import sys
import logging
import argparse
import cv2

import flare_bypasser

if __name__ == '__main__':
  logging.basicConfig(
    format='%(asctime)s [%(name)s] [%(levelname)s]: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.INFO
  )
  parser = argparse.ArgumentParser(
    description='Recognize flare checkbox position by image (allow to debug flare-bypasser).',
  )
  parser.add_argument("image", type=str)
  parser.add_argument("--debug-dir", type=str, default=None)
  parser.add_argument("--verbose", action='store_true')
  parser.set_defaults(verbose=False)
  args = parser.parse_args()
  image = cv2.imread(args.image)
  if args.verbose:
    logger = logging.getLogger('flare_bypasser.recognizing')
    logger.setLevel(logging.DEBUG)
  else:
    logger = None

  print("args.debug_dir: " + str(args.debug_dir))
  click_point = flare_bypasser.Solver.get_flare_click_point(
    image, save_steps_dir=args.debug_dir, logger=logger)
  if click_point:
    print("Recognized checkbox click point: " + str(click_point))
    sys.exit(0)
  else:
    print("Can't find checkbox", file=sys.stderr)
    sys.exit(1)
