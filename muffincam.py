import argparse
import warnings
import datetime
import imutils
import json
import time
import cv2

from pyimagesearch.tempimage import TempImage
from dropbox.client import DropboxOAuth2FlowNoRedirect
from dropbox.client import DropboxClient
from picamera.array import PiRGBArray
from picamera import PiCamera

# parse command line arguments
ap = argparse.ArgumentParser()
ap.add_argument("-c", "--config", required=True,
                help="Path to the json configuration file")
args = vars(ap.parse_args())

warnings.filterwarnings("ignore")
conf = json.load(open(args["config"]))
client = None

# sync captured images with Dropbox
if conf["use_dropbox"]:
    flow = DropboxOAuth2FlowNoRedirect(conf["dropbox_key"],
                                       conf["dropbox_secret"])
    print "[INFO] Authorize this application: {}".format(flow.start())
    authCode = raw_input("Enter auth code: ").strip()

    (acessToken, userID) = flow.finish(authCode)
    client = DropboxClient(acessToken)
    print "[SUCCESS] dropbox account linked"

# access to Raspberry Pi camera
camera = PiCamera()
resolution = tuple(conf["resolution"])
camera.resolution = resolution
camera.framerate = conf["fps"]
rawCapture = PiRGBArray(camera, size=resolution)

print "[INFO] warming up..."
time.sleep(conf["camera_warmup_time"])
avg = None
timestamp = datetime.datetime.now()
lastUpLoaded = datetime.datetime.now()

# only consecutive motions trigger a real motion
motionCounter = 0

for frame in camera.capture_continuous(rawCapture, format="bgr",
                                       use_video_port=True):
    frame = frame.array()
    text = "Unoccupied"

    frame = imutils.resize(frame, width=500)

    # convert to grayscale before processing
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    if avg is None:
        print "[INFO] starting background model..."
        avg = gray.copy().astype("float")
        rawCapture.truncate(0)
        continue

    cv2.acculateWeighted(gray, avg, 0.5)
    frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))
    thresh = cv2.threshold(frameDelta, conf["delta_thresh"],
                           255, cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, iterations=2)
    (cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
                                 cv2.CHAIN_APPROX_SIMPLE)

    for c in cnts:
        if cv2.contourArea(c) < conf["min_area"]:
            continue

        (x, y, w, h) = cv2.boundingRect(c)
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        text = "Occupied"

    cv2.putText(frame, "Room Status: {0}".format(text), (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    ts = timestamp.strftime("%A %d %B %Y %H:%M:%S")
    cv2.putText(frame, ts, (10, frame.shape[0]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

    if text == "Occupied":
        if (timestamp - lastUpLoaded).seconds >= conf["min_upload_seconds"]:
            motionCounter += 1

            if motionCounter >= conf["min_motion_frames"]:
                if conf["use_dropbox"]:
                    t = TempImage()
                    cv2.imwrite(t.path, frame)

                    print "[UPLOAD {}".format()
                    path = "{base_path}/{timestamp}.jpg".format(
                        base_path=conf["dropbox_base_path"], timestamp=ts)
                    client.put_file(path, open(t.path, "rb"))

                    lastUpLoaded = timestamp
                    motionCounter = 0
    else:
        motionCounter = 0

    if conf["show_video"]:
        cv2.imshow("Security Feed", frame)

        if cv2.waitKey(1) == ord("q"):
            break

    rawCapture.truncate(0)

camera.release()
cv2.destroyAllWindows()
