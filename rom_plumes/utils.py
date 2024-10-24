import glob
import os
import sys
import time
from logging import getLogger
from logging import Logger
from logging import StreamHandler
from typing import Optional
from warnings import warn

import cv2
import imageio
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from moviepy.editor import VideoFileClip
from PIL import Image
from tqdm import tqdm

from .typing import ColorImage
from .typing import Contour_List
from .typing import Float2D
from .typing import GrayImage
from .typing import NpFlt
from .typing import X_pos
from .typing import Y_pos

logger = getLogger(__name__)
handler = StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
logger.setLevel("INFO")


# display utils
def add_clock(f):
    def _rename_string(f_name):
        if f_name == "video_to_ROM":
            return "apply concentric circle"
        if f_name.startswith("apply"):
            return f_name.replace("_", " ")
        return "apply " + f_name.replace("_", " ")

    def clocked_f(*args, **kwargs):
        f_name = _rename_string(f.__name__)
        t0 = time.perf_counter()
        result = f(*args, **kwargs)
        elapsed_time = time.perf_counter() - t0
        logger.info(f_name + ": " + "[%0.4fs]" % elapsed_time)
        return result

    return clocked_f


def _warn_external(
    message: str, loggr: Optional[Logger] = None, category: Optional[type] = None
):
    """Convenience function to print a warning to the log, but also create a Warning

    This allows warnings to be caught and debugged by the warnings filter, but also
    appear in any concurrent log
    """
    if loggr is not None:
        loggr.warn(message, stacklevel=2)
    warn(message, category, stacklevel=2)


# Math Functions
def circle_intersection(x0, y0, r0, x1, y1, r1):
    """
    Find the intersections of a circle centered at (x0,y0) with radii
    r0 with a circle centered at (x1,y1) with radii r1.

    source:
    https://math.stackexchange.com/questions/256100/how-can-i-find-the-points-at-which-two-circles-intersect
    """

    d = np.sqrt((x0 - x1) ** 2 + (y0 - y1) ** 2)
    L = (r0**2 - r1**2 + d**2) / (2 * d)
    h = np.sqrt(r0**2 - L**2)

    x3 = L / d * (x1 - x0) - h / d * (y1 - y0) + x0
    y3 = L / d * (y1 - y0) + h / d * (x1 - x0) + y0

    x4 = L / d * (x1 - x0) + h / d * (y1 - y0) + x0
    y4 = L / d * (y1 - y0) - h / d * (x1 - x0) + y0

    sol = np.array([[x3, y3], [x4, y4]])

    return sol


def circle_poly_intersection(r, x0, y0, poly_coef):
    """
    Find roots of function F where
    F(x) = (x - x0)**2 + (y(x)-y0)**2 - r**2

    where y(x) = a0 + a1 x + ... + an x^n is the polynomial
    with coef poly_coef = [a0, a1, ..., an] in ascending order.

    Parameters:
    ----------
    r:
        radii of circle

    x0,y0:
        center of circle

    poly_coef:
        coefficients of polynomial function in ascending degree order.

    Returns:
    -------
    np.ndarray:
        Array of solutions
    """
    if len(poly_coef) == 1:
        F_coef = [x0**2 + (y0 - poly_coef[0]) ** 2 - r**2, -2 * x0, 1]
    else:
        F_coef = _square_poly_coef(poly_coef)
        F_coef[: len(poly_coef)] += -2 * y0 * np.array(poly_coef)
        F_coef[0] += x0**2 + y0**2 - r**2
        F_coef[1] += -2 * x0
        F_coef[2] += 1

    roots = np.polynomial.polynomial.polyroots(F_coef)
    roots = np.real(roots[np.isreal(roots)])

    y_poly = np.polynomial.Polynomial(poly_coef)

    sol = []
    for x in roots:
        sol.append([x, y_poly(x)])

    return np.array(sol)


def _square_poly_coef(coef: tuple[any]) -> np.ndarray[tuple[any], NpFlt]:
    """
    coef of poly in ascend/descend order. Results returned in same order.

    Parameters:
    ----------
    coef:
        List of poly coefficients, coef = [a0, a1, ..., an], where
        P(x) = a0 + a1 x + ... +an x^n.


    Returns:
    -------
        np.ndarray:
            Coefficients of squared polynomial [c0, c1, ..., c2n], where
            P^2(x) = c0 + c1 x + .. + c2n x^2n.

            ck = sum ai * a_(k-i) for i in range(k)
    """

    def a_i(i):
        if i < len(coef):
            return coef[i]
        return 0

    def n_coef(n):
        return np.sum([a_i(i) * a_i(n - i) for i in range(n + 1)])

    return np.array([n_coef(n) for n in range(2 * len(coef) - 1)])


#############################
# General Purpose functions #
#############################


# General Purpose functions
def count_files(directory: str, extension: str) -> int:
    """
    Return the number of items in directory ending with a certain extension.

    Args:
        directory (str): Directory path containing files
        extension (str): Extension of interest, e.g. "png", "jpg".

    Returns:
        int: Count for number of files in directory.

    """
    count = 0

    # Iterate over the files in the given directory
    for filename in os.listdir(directory):
        # Check if the file has extension
        if filename.endswith("." + extension):
            count += 1
    return count


def create_directory(directory):
    # Create the directory if it does not exist
    if not os.path.exists(directory):
        os.makedirs(directory)
        # print(f"Directory '{directory}' created.")
    # else:
    #     print(f"Directory '{directory}' already exists.")


# For extracting frames from video
def extract_all_frames(video_path, save_path="frames", extension="png"):
    """
    To extract all frames from a video.

    Args:
        video_path (str): path to video
        save_path (str): folder name of save frames
        extension (str): file type to save frames as e.g., "png", "jpg"
    """
    clip = VideoFileClip(video_path)
    total_frames = int(clip.fps * clip.duration)

    frame_mag = len(str(total_frames))

    create_directory(save_path)

    for frame_number in range(total_frames):
        frame_time = frame_number / clip.fps
        frame = clip.get_frame(frame_time)

        # Modified Code to have consistent nomenclature
        if len(str(frame_number)) < frame_mag:
            num_of_lead_zeros = frame_mag - len(str(frame_number))
            frame_str = ""
            for i in range(num_of_lead_zeros):
                frame_str += "0"
            frame_number = frame_str + str(frame_number)

        if not isinstance(frame_number, str):
            frame_number = str(frame_number)

        frame_path = f"{save_path}/frame_" + frame_number + "." + extension
        imageio.imwrite(frame_path, frame)


# Functions for subtracting frames
def create_id(id, magnitude):
    num_of_leading_zeros = magnitude - len(str(id))
    frame_str = ""
    for i in range(num_of_leading_zeros):
        frame_str += "0"
    frame_number = frame_str + str(id)
    return frame_number


def get_frame_ids(directory: str, extension: str = "png") -> list:
    """
    Return list of items in directory ending with a certain extension.

    Args:
        directory (str): Directory path containing files
        extension (str): Extension of interest, e.g. "png", "jpg".

    Returns:
        list: List of files in directory.

    """
    file_ids = []

    # Iterate over the files in the given directory
    for filename in os.listdir(directory):
        # Check if the file has desired extension
        if filename.endswith("." + extension):
            file_ids.append(filename)
            # print(file_ids)
    file_ids.sort()
    return file_ids


############################
# Edge detection functions #
############################


# ADD variables for hyperparameter tuning
def edge_detect(
    frames_path,
    extension="png",
    save_path="edge_frames",
    d=10,
    sigmaColor=20,
    sigmaSpace=20,
    t_lower=5,
    t_upper=10,
):
    """
    Uses Bilaterial filtering in conjunction with opencv edge detection.
    """

    # Get list of frames [frame_0000.png, ...]
    frames_id = get_frame_ids(directory=frames_path, extension=extension)

    # Create directory to save subtracted frames
    create_directory(save_path)

    frames_mag = len(str(len(frames_id)))

    count = 0
    for frame in frames_id:
        img_path = os.path.join(frames_path, frame)
        img = cv2.imread(img_path)

        # convert to gray
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Apply Bilateral filter smoothing without removing edges.
        gray_filtered = cv2.bilateralFilter(
            gray, d=d, sigmaColor=sigmaColor, sigmaSpace=sigmaSpace
        )

        # Use Canny to get edge contours
        edges_filtered = cv2.Canny(
            gray_filtered, threshold1=t_lower, threshold2=t_upper
        )

        # save edge detected frame
        new_id = create_id(count, frames_mag)
        file_name = "edge_" + new_id + "." + extension
        cv2.imwrite(os.path.join(save_path, file_name), edges_filtered)

        count += 1
    return


######################
# Finding Plume Path #
######################

# Class for having users pick initial center for plume detection


class ImagePointPicker:
    def __init__(self, img_path):
        self.img_path = img_path
        self.clicked_point = None

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.clicked_point = (x, y)
            # print(f"Clicked at ({x}, {y})")
            cv2.destroyAllWindows()

    def ask_user(self):
        image = cv2.imread(self.img_path)
        image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        cv2.namedWindow("Image")
        cv2.setMouseCallback("Image", self.mouse_callback)

        cv2.imshow("Image", image_gray)

        while self.clicked_point is None:
            cv2.waitKey(1)

        # print("Clicked point:", self.clicked_point)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()


class VideoPointPicker:
    def __init__(self, video_path):
        self.video_path = video_path
        self.video_capture = cv2.VideoCapture(video_path)
        self.clicked_point = None

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.clicked_point = (x, y)
            print(f"Clicked at ({x}, {y})")
            cv2.destroyAllWindows()

    def ask_user(self):
        video_cap = self.video_capture
        tot_frames = int(video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        middle_frame_id = tot_frames // 2
        video_cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame_id)

        ret, frame = video_cap.read()

        if ret:
            cv2.namedWindow("Image")
            cv2.setMouseCallback("Image", self.mouse_callback)
            cv2.imshow("Image", frame)

            while self.clicked_point is None:
                cv2.waitKey(1)


###################
# Post Processing #
###################


# For saving frames as video
def create_video(directory, output_file, fps=15, extension="png", folder="movies"):
    """
    Create video from selected frames

    Args:
        directory (str): Directory of where to access png files
        output_file (str): path and name of file to save, e.g., [path/]video.mp4
        fps (int): Specify the frames per second for video.
    """
    # Create directory to store movies
    create_directory(folder)

    # Get the list of PNG files in the directory
    png_files = sorted(
        [file for file in os.listdir(directory) if file.endswith("." + extension)]
    )

    # Get the first image to retrieve its dimensions
    first_image = cv2.imread(os.path.join(directory, png_files[0]))
    height, width, _ = first_image.shape

    # Create a video writer object
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    video_writer = cv2.VideoWriter(output_file, fourcc, fps, (width, height))

    # Write each image to the video writer
    for png_file in tqdm(png_files):
        image_path = os.path.join(directory, png_file)
        image = cv2.imread(image_path)
        video_writer.write(image)

    # Release the video writer and close the file
    video_writer.release()


def create_gif(
    frames_dir: str,
    duration: int,
    frames_range: list = None,
    rotate_ang: float = 0,
    gif_name: str = "animation",
    extension: str = "png",
):
    """
    Create GIF from specified frames directory.

    Args:
        frames_dir (str): directory path containing frames
        duration (int): Number of milliseconds
        frames_range (list): frames of interest for gif
        rorate_ang (float): counter clock-wise
        gif_name (str): name to be given
        extension (str): extension type to search for in directory
    """

    def add_forward_slash(string):
        if not string.endswith("/"):
            string += "/"
        return string

    # start_frame, end_frame = frames_range

    # Add '/' to path if it does not already exist
    frames_dir = add_forward_slash(frames_dir)

    # Get all files with specified extension in frames_dir
    frame_paths = sorted(glob.glob(frames_dir + "*." + extension))

    # Select appropriate frame range - default None is all frames
    if frames_range is None:
        frame_paths = frame_paths
    elif isinstance(frames_range, list) and len(frames_range) == 2:
        start_frame, end_frame = frames_range
        frame_paths = frame_paths[start_frame:end_frame]
    elif isinstance(frames_range, int):
        start_frame = frames_range
        frame_paths = frame_paths[start_frame:]
    else:
        raise ValueError("frames_range must be a 2 int list, or a single int.")

    # Instantiate list to store image files
    frames = []

    # Iterate over each frame in file
    for path in tqdm(frame_paths):
        # path = frame_paths[i]

        # Open the frame as image
        image = Image.open(path)

        # Append the image to the frames list
        frames.append(image.rotate(rotate_ang))

    # Save frames as animated gif
    frames[0].save(
        gif_name + ".gif",
        format="GIF",
        append_images=frames[1:],
        duration=duration,
        save_all=True,
        loop=0,
    )


def create_vari_dist_movie(vari_dist, save_path=None):
    """
    Create movie directly form vari_dist data attained from
    PLUME.train(). In PLUME.var1_dist and PLUME.var2_dist.
    """

    # find max r and d
    max_r = 0
    max_d = 0
    for vari in vari_dist:
        if len(vari[1]) != 0:
            max_r_i = np.max(vari[1][:, 0])
            if max_r_i >= max_r:
                max_r = max_r_i
            max_d_i = np.max(vari[1][:, 1])
            if max_d_i >= max_d:
                max_d = max_d_i

    # function to generate plots
    def generate_plot(frame):
        plt.clf()
        t, r_d_arr = vari_dist[frame]
        plt.title(f"Var (r, d), t={t}")
        if len(r_d_arr) != 0:
            plt.scatter(r_d_arr[:, 0], r_d_arr[:, 1], c="blue")
        plt.xlim(0, max_r)
        plt.ylim(0, max_d)
        plt.xlabel("r (flattened p_mean)")
        plt.ylabel("d")

    # Create movie
    fig = plt.figure()
    ani = FuncAnimation(fig, generate_plot, frames=len(vari_dist), interval=100)
    if isinstance(save_path, str):
        ani.save(save_path, writer="ffmpeg", fps=10)
        plt.show()


def create_ROM_plume_movie(
    PLUME_object,
    frame_range: int | list[int] | None = None,
    save_path: str | None = None,
) -> None:
    """
    Create the ROM plume movie using the trained PLUME model
    """

    if frame_range is None:
        num_frames = len(PLUME_object.mean_poly)
    elif isinstance(frame_range, int):
        num_frames = range(frame_range, len(PLUME_object.mean_poly))
    elif isinstance(frame_range, list):
        num_frames = range(frame_range[0], frame_range[1])

    def generate_plot(frame):
        PLUME_object.plot_ROM_plume(frame, show_plot=False)

    fig = plt.figure()
    ani = FuncAnimation(fig, generate_plot, frames=num_frames)

    if isinstance(save_path, str):
        if save_path.endswith(".mp4") is False:
            save_path += ".mp4"
        ani.save(save_path, writer="ffmpeg", fps=15)
        plt.show()


def _add_contours_on_img(
    img: GrayImage | ColorImage,
    orig_center: Optional[tuple[X_pos, Y_pos]] = None,
    mean_scatter: Optional[Float2D] = None,
    var1_scatter: Optional[Float2D] = None,
    var2_scatter: Optional[Float2D] = None,
    selected_contours: Contour_List = None,
    radii: Optional[int] = None,
    num_of_circs: Optional[int] = None,
    interior_scale: Optional[float] = None,
    mean_scatter_color=(0, 0, 255),
    var1_scatter_color=(255, 0, 0),
    var2_scatter_color=(255, 0, 255),
    ring_color=(255, 0, 0),
    interior_ring_color=(0, 0, 255),
    contour_color=(0, 255, 0),
) -> ColorImage:
    """
    Apply optional contour plotting to img.

    Returns:
    -------
    color_img:
        Colored frame with contour plotting applied.
    """

    if len(img.shape) == 2:
        color_img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif len(img.shape) == 3:
        color_img = img.copy()

    if mean_scatter is not None:
        for x_y in mean_scatter:
            cv2.circle(color_img, x_y.astype(int), 7, mean_scatter_color, -1)

    if var1_scatter is not None:
        for x_y in var1_scatter:
            cv2.circle(color_img, x_y.astype(int), 7, var1_scatter_color, -1)

    if var2_scatter is not None:
        for x_y in var2_scatter:
            cv2.circle(color_img, x_y.astype(int), 7, var2_scatter_color, -1)

    if selected_contours:
        cv2.drawContours(color_img, selected_contours, -1, contour_color, 2)

    if radii and num_of_circs and orig_center:
        for step in range(1, num_of_circs + 1):
            radius_i = radii * step

            cv2.circle(
                color_img,
                center=orig_center,
                radius=radius_i,
                color=ring_color,
                thickness=1,
                lineType=cv2.LINE_AA,
            )
    if interior_scale and mean_scatter is not None:
        for i, point in enumerate(mean_scatter[1:]):
            i += 2
            radius_i = radii * i
            cv2.circle(
                color_img,
                center=point.astype(np.uint8),
                radius=int(radius_i * interior_scale),
                color=interior_ring_color,
                thickness=1,
                lineType=cv2.LINE_AA,
            )

    return color_img
