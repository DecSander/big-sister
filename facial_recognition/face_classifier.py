import face_recognition as fr
import os

from itertools import compress


class FaceClassifier(object):
    """
    Naive implementation for face classification
    """

    def __init__(self, directory='known_faces'):
        # assumes directory includes only .jpg files
        self.files = os.listdir(directory)
        self.encodings = [fr.face_encodings(fr.load_image_file(directory + '/' + f))[0] for f in self.files]

    def classify(self, file):
        unknown_encoding = fr.face_encodings(fr.load_image_file(file))[0]
        results = fr.compare_faces(self.encodings, unknown_encoding)
        if sum(results) == 0:
            return 'Unknown Face'
        return list(compress(self.files, results))[0][:-4]


def main():
    classifier = FaceClassifier()

    print "Classifying unknown face..."
    print classifier.classify("unknown.jpg")

    print "Classifying known face..."
    print classifier.classify("known.jpg")


if __name__ == '__main__':
    main()
