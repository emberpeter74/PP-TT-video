"""Step 6, part 1: find other cars in a picture.

A ready-made model from the torchvision library does the finding. It was
trained by others on a large set of everyday photos and knows what cars,
trucks and buses look like. For every picture it returns boxes around the
things it recognises, each with a confidence between 0 and 1.
"""

from dataclasses import dataclass

from pp_tt_video import settings


@dataclass(frozen=True)
class CarBox:
    """A box around one car in one picture. Positions are in pixels."""

    left: float
    top: float
    right: float
    bottom: float
    confidence: float   # how sure the model is, from 0 to 1

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    @property
    def centre(self):
        return ((self.left + self.right) / 2, (self.top + self.bottom) / 2)


def keep_car_boxes(boxes, picture_width):
    """Drop the boxes that cannot be another car.

    A very wide box is the model mistaking the own cockpit for a vehicle.
    """
    limit = picture_width * settings.MAX_CAR_WIDTH_FRACTION
    return [box for box in boxes if box.width <= limit]


class CarDetector:
    """Loads the model once and then finds cars in as many pictures as asked."""

    def __init__(self, use_graphics_card=None):
        # torch is imported here, not at the top of the file, so that the
        # parts of the project that do not need it also run without it.
        import torch
        from torchvision.models import detection

        if use_graphics_card is None:
            use_graphics_card = settings.USE_GRAPHICS_CARD
        self.torch = torch
        self.device = "cuda" if use_graphics_card and torch.cuda.is_available() else "cpu"

        # "Weights" are the numbers the model learned during training. They
        # are downloaded once (about 170 MB) and kept on this PC afterwards.
        weights = detection.FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT
        self.model = detection.fasterrcnn_resnet50_fpn_v2(
            weights=weights,
            box_score_thresh=settings.MIN_DETECTION_CONFIDENCE,
        )
        self.model.eval()            # "eval" = use the model, do not train it
        self.model.to(self.device)

        # The model answers with numbers; this turns them into names.
        names = weights.meta["categories"]
        self.vehicle_numbers = {number for number, name in enumerate(names) if name in settings.VEHICLE_NAMES}

    def detect(self, frames):
        """Find the cars in a list of frames.

        Returns one list of CarBox per frame, in the same order.
        """
        return [
            keep_car_boxes(boxes, frame.width)
            for boxes, frame in zip(self.detect_raw(frames), frames)
        ]

    def detect_raw(self, frames):
        """Find every vehicle the model sees in a list of frames.

        Like detect, but nothing is thrown away yet: the boxes that cannot
        be another car (the own cockpit) are still in the lists. These raw
        boxes are what is saved, so that the check video can show what was
        thrown away.
        """
        torch = self.torch
        pictures = []
        for frame in frames:
            # Turn the raw bytes into a table of numbers the model can read:
            # 3 colours x height x width, with values between 0 and 1.
            picture = torch.frombuffer(bytearray(frame.pixels), dtype=torch.uint8)
            picture = picture.reshape(frame.height, frame.width, 3).permute(2, 0, 1)
            pictures.append(picture.to(self.device).float() / 255)

        # no_grad: we only want answers, so skip the bookkeeping for training.
        # autocast: calculate with shorter numbers on the graphics card, which
        # is faster and makes no practical difference to the result.
        with torch.no_grad(), torch.autocast(self.device, enabled=self.device == "cuda"):
            answers = self.model(pictures)

        results = []
        for frame, answer in zip(frames, answers):
            boxes = []
            for position, number, confidence in zip(
                answer["boxes"].tolist(), answer["labels"].tolist(), answer["scores"].tolist()
            ):
                if number in self.vehicle_numbers:
                    boxes.append(CarBox(*position, confidence))
            results.append(boxes)
        return results
