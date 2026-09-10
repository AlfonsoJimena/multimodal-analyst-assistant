from cameras import PICamera
import cv2

# RESOLUTIONS
HIGHRES_SIZE = (1280, 720)
LARGE_SIZE = (640, 480)
SMALL_SIZE = (320, 200)

FPS = 30

def main():
    cam = PICamera(recording_res = HIGHRES_SIZE)
    cam.start()
	
    while(True):
        image_rgb = cam.read_frame()
        
        if image_rgb is None:
            continue
        
        cv2.imshow("Emotions classifier", image_rgb)
        
        key = cv2.waitKey(int(1 / FPS * 1000)) & 0xFF
        if key == ord("q"):
            break
        

if __name__ == "__main__":
    main()
