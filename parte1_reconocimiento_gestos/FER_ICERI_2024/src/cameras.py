import cv2
from time import sleep


class Camera:
    def read_frame(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass


class CVCamera(Camera):
    def __init__(self, recording_res, index_cam=0):
        self.index_cam = index_cam
        self.rec_res = recording_res

    def read_frame(self):
        ret, frame = self.vid.read()
        return frame

    def start(self):
        self.vid = cv2.VideoCapture(self.index_cam)
        self.vid.set(cv2.CAP_PROP_FRAME_WIDTH, self.rec_res[0])
        self.vid.set(cv2.CAP_PROP_FRAME_HEIGHT, self.rec_res[1])

    def stop(self):
        self.vid.release()

    def close(self):
        self.vid.release()


class PICamera(Camera):
    def __init__(self, recording_res):
        try:
            from picamera2 import Picamera2, Preview
            import libcamera

            self.picam2 = Picamera2()
            self.Preview = Preview
            preview_config = self.picam2.create_preview_configuration(
                main={"size": recording_res[::-1]},
                controls={
                    "AwbEnable": False,
                    # "AwbMode": libcamera.controls.AwbModeEnum.Indoor,
                    "AwbMode": libcamera.controls.AwbModeEnum.Auto,
                    "AnalogueGain": 1.0,
                },
            )
            self.picam2.configure(preview_config)

        except ModuleNotFoundError:
            print(
                "Cannnot initialize PiCamera on this device. Check if you are using a Raspberry Pi and it is up to date."
            )
            exit()

    def start(self):
        # self.picam2.start_preview(self.Preview.QTGL)
        self.picam2.start()

    def close(self):
        self.picam2.close()

    def read_frame(self):
        image_bgr = self.picam2.capture_array("main")
        # Depending on the raspberry orientation
        image_bgr = cv2.rotate(image_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        return image_rgb
