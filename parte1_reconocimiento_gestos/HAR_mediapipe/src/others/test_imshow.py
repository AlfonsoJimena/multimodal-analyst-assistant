import cv2

#read image 
img = cv2.imread('/home/pi/workspace/image_recognition/data/telephone/telephone0000.jpg')
 
#show image
cv2.imshow('Example - Show image in window',img)
 
cv2.waitKey(0) # waits until a key is pressed
cv2.destroyAllWindows() # destroys the window showing image
