import math
from datetime import datetime
from datetime import timedelta
import time
import ephem
import numpy
import cv2
import logging


logger = logging.getLogger('indi_allsky')


class LightGraphOverlay(object):

    text_area_height = 100


    def __init__(self, config, position_av):
        self.config = config
        self.position_av = position_av

        self.lightgraph = None
        self.next_generate = 0  # generate immediately


        self.graph_height = self.config.get('LIGHTGRAPH_OVERLAY', {}).get('GRAPH_HEIGHT', 50)
        self.graph_border = self.config.get('LIGHTGRAPH_OVERLAY', {}).get('GRAPH_BORDER', 3)
        self.now_marker_size = self.config.get('LIGHTGRAPH_OVERLAY', {}).get('NOW_MARKER_SIZE', 8)
        self.day_color = list(self.config.get('LIGHTGRAPH_OVERLAY', {}).get('DAY_COLOR', (200, 200, 200)))
        self.night_color = list(self.config.get('LIGHTGRAPH_OVERLAY', {}).get('NIGHT_COLOR', (15, 15, 15)))
        self.hour_color = list(self.config.get('LIGHTGRAPH_OVERLAY', {}).get('HOUR_COLOR', (15, 15, 100)))
        self.border_color = list(self.config.get('LIGHTGRAPH_OVERLAY', {}).get('BORDER_COLOR', (1, 1, 1)))
        self.now_color = list(self.config.get('LIGHTGRAPH_OVERLAY', {}).get('NOW_COLOR', (15, 150, 200)))
        self.font_color = list(self.config.get('LIGHTGRAPH_OVERLAY', {}).get('FONT_COLOR', (200, 200, 200)))
        self.opacity = self.config.get('LIGHTGRAPH_OVERLAY', {}).get('OPACITY', 100)

        self.label = self.config.get('LIGHTGRAPH_OVERLAY', {}).get('LABEL', False)
        self.hour_lines = self.config.get('LIGHTGRAPH_OVERLAY', {}).get('HOUR_LINES', True)


    def main(self):
        now = time.time()

        if now > self.next_generate:
            self.lightgraph = self.generate()


        lightgraph = self.lightgraph.copy()


        graph_height, graph_width = lightgraph.shape[:2]


        now = datetime.now()
        noon = datetime.strptime(now.strftime('%Y%m%d12'), '%Y%m%d%H')

        now_offset = int((now - noon).seconds / 60) + self.graph_border


        # draw now triangle
        now_tri = numpy.array([
            (now_offset - self.now_marker_size, (self.graph_height + self.graph_border) - self.now_marker_size),
            (now_offset + self.now_marker_size, (self.graph_height + self.graph_border) - self.now_marker_size),
            (now_offset, self.graph_height + self.graph_border),
        ],
            dtype=numpy.int32,
        )
        #logger.info(now_tri)

        cv2.fillPoly(
            img=lightgraph,
            pts=[now_tri],
            color=self.now_color,
        )


        # create alpha channel, anything pixel that is full black (0, 0, 0) is transparent
        alpha = numpy.max(lightgraph, axis=2)
        alpha[alpha > 0] = int(255 * (self.opacity / 100))
        lightgraph = numpy.dstack((lightgraph, alpha))


        # separate layers
        lightgraph_bgr = lightgraph[:, :, :3]
        lightgraph_alpha = (lightgraph[:, :, 3] / 255).astype(numpy.float32)

        # create alpha mask
        alpha_mask = numpy.dstack((
            lightgraph_alpha,
            lightgraph_alpha,
            lightgraph_alpha,
        ))


        # apply alpha mask
        lightgraph_final = (self.random_rgb * (1 - alpha_mask) + lightgraph_bgr * alpha_mask).astype(numpy.uint8)


        if self.label:
            self.drawText_opencv(lightgraph_final)


        #cv2.imwrite('lightgraph.png', lightgraph_final, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        cv2.imwrite('lightgraph.jpg', lightgraph_final, [cv2.IMWRITE_JPEG_QUALITY, 90])


    def generate(self):
        generate_start = time.time()


        now = datetime.now()
        utc_offset = now.astimezone().utcoffset()

        noon = datetime.strptime(now.strftime('%Y%m%d12'), '%Y%m%d%H')
        self.next_generate = (noon + timedelta(hours=24)).timestamp()

        noon_utc = noon - utc_offset


        obs = ephem.Observer()
        obs.lat = math.radians(self.position_av[0])
        obs.lon = math.radians(self.position_av[1])

        # disable atmospheric refraction calcs
        obs.pressure = 0

        sun = ephem.Sun()


        lightgraph_list = list()
        for x in range(1440):
            obs.date = noon_utc + timedelta(minutes=x)
            sun.compute(self.obs)

            sun_alt_deg = math.degrees(self.sun.alt)

            if sun_alt_deg < -18:
                lightgraph_list.append(self.night_color)
            elif sun_alt_deg > 0:
                lightgraph_list.append(self.day_color)
            else:
                norm = (18 + sun_alt_deg) / 18  # alt is negative
                lightgraph_list.append(self.mapColor(norm, self.day_color, self.night_color))

        #logger.info(lightgraph_list)

        generate_elapsed_s = time.time() - generate_start
        logger.warning('Total lightgraph processing in %0.4f s', generate_elapsed_s)


        lightgraph = numpy.array([lightgraph_list], dtype=numpy.uint8)
        lightgraph = cv2.resize(
            lightgraph,
            (1440, self.graph_height),
            interpolation=cv2.INTER_AREA,
        )


        if self.hour_lines:
            # draw hour ticks
            for x in range(1, 24):
                cv2.line(
                    img=lightgraph,
                    pt1=(60 * x, 0),
                    pt2=(60 * x, self.graph_height),
                    color=tuple(self.hour_color),
                    thickness=1,
                    lineType=self.line_type,
                )


        # draw border
        lightgraph = cv2.copyMakeBorder(
            lightgraph,
            self.graph_border,
            self.graph_border,
            self.graph_border,
            self.graph_border,
            cv2.BORDER_CONSTANT,
            None,
            self.border_color,
        )


        # draw text area
        lightgraph = cv2.copyMakeBorder(
            lightgraph,
            0,
            self.text_area_height,
            0,
            0,
            cv2.BORDER_CONSTANT,
            None,
            (0, 0, 0)
        )


        return lightgraph


    def drawText_opencv(self, lightgraph, font_color_bgr):
        fontFace = getattr(cv2, self.config['TEXT_PROPERTIES']['FONT_FACE'])
        lineType = getattr(cv2, self.config['TEXT_PROPERTIES']['FONT_AA'])

        for x, hour in enumerate([13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]):
            cv2.putText(
                img=lightgraph,
                text=str(hour),
                org=((60 * (x + 1)) - 10, self.graph_height + (self.graph_border * 2) + 20),
                fontFace=fontFace,
                color=(1, 1, 1),  # not full black
                lineType=lineType,
                fontScale=self.config['TEXT_PROPERTIES']['FONT_SCALE'],
                thickness=self.config['TEXT_PROPERTIES']['FONT_THICKNESS'] + 1,
            )
            cv2.putText(
                img=lightgraph,
                text=str(hour),
                org=((60 * (x + 1)) - 10, self.graph_height + (self.graph_border * 2) + 20),
                fontFace=fontFace,
                color=tuple(font_color_bgr),
                lineType=lineType,
                fontScale=self.config['TEXT_PROPERTIES']['FONT_SCALE'],
                thickness=self.config['TEXT_PROPERTIES']['FONT_THICKNESS'] + 1,
            )


    def mapColor(self, scale, color_high, color_low):
        return tuple(int(((x[0] - x[1]) * scale) + x[1]) for x in zip(color_high, color_low))
