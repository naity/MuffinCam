import uuid
import os


class TempImage(object):
    def __init__(self, basePath="./", ext=".jpg"):
        self.path = "{base_path}/{rand}{ext}".format(base_path=basePath,
                    rand=str(uuid.uuid4()), ext=ext)

    def cleanup(self):
        os.remove(self.path)
