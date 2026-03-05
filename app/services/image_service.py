from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
from typing import Optional
from PIL import Image, ImageFilter, ImageOps
import logging
from app.schemas.common import ImageBox

logger = logging.getLogger("uvicorn.error")

# Centralized tuning parameters for OCR image cleanup and diagram extraction.
# Keep these values in one place so we can iterate without changing algorithm flow.
RED_MARK_R_MIN = 125
RED_MARK_R_OVER_G = 1.18
RED_MARK_R_OVER_B = 1.18

OTSU_DEFAULT_THRESHOLD = 140
OTSU_MIN_THRESHOLD = 60
OTSU_MAX_THRESHOLD = 210

DIAGRAM_COMPONENT_MIN_AREA_RATIO = 0.0001
DIAGRAM_COMPONENT_MIN_AREA_PIXELS = 18
DIAGRAM_COMPONENT_DENSITY_MIN = 0.03
DIAGRAM_COMPONENT_ASPECT_MIN = 0.20
DIAGRAM_COMPONENT_ASPECT_MAX = 8.0

DIAGRAM_CLUSTER_GAP_X_RATIO = 0.015
DIAGRAM_CLUSTER_GAP_Y_RATIO = 0.020
DIAGRAM_CLUSTER_GAP_X_MIN = 10
DIAGRAM_CLUSTER_GAP_Y_MIN = 8
DIAGRAM_CLUSTER_UPPER_BIAS_Y_RATIO = 0.62
DIAGRAM_CLUSTER_UPPER_BIAS_FACTOR = 1.08

DIAGRAM_ALPHA_DILATE_SIZE = 3
DIAGRAM_CUTOUT_PAD_X_RATIO = 0.04
DIAGRAM_CUTOUT_PAD_Y_RATIO = 0.06
DIAGRAM_CUTOUT_PAD_X_MIN = 8
DIAGRAM_CUTOUT_PAD_Y_MIN = 6
DIAGRAM_CUTOUT_MIN_AREA_RATIO = 0.62

FOREGROUND_DARK_PIXEL_THRESHOLD = 150
FOREGROUND_PROFILE_BASE_THRESHOLD = 0.03
FOREGROUND_PROFILE_PEAK_THRESHOLD_RATIO = 0.45
FOREGROUND_PROFILE_MIN_PEAK = 0.01
FOREGROUND_PREFER_TOP_MIN_LEN_RATIO = 0.06
FOREGROUND_PREFER_TOP_MIN_LEN_PIXELS = 8
FOREGROUND_SEGMENT_LENGTH_WEIGHT_POWER = 0.35
FOREGROUND_UPPER_BIAS_Y_RATIO = 0.62
FOREGROUND_UPPER_BIAS_FACTOR = 1.2
FOREGROUND_MAX_HEIGHT_RATIO = 0.82
FOREGROUND_TRIM_HEIGHT_RATIO = 0.72
FOREGROUND_PAD_RATIO = 0.06
FOREGROUND_PAD_MIN = 4
FOREGROUND_MIN_AREA_RATIO = 0.08

BG_FLATTEN_BLUR_RADIUS_RATIO = 0.03
BG_FLATTEN_BLUR_RADIUS_MIN = 6
BG_FLATTEN_GAIN_TARGET = 220.0
BG_FLATTEN_GAIN_MIN = 0.75
BG_FLATTEN_GAIN_MAX = 1.65
BG_FLATTEN_LIGHT_BOOST = 18

MEANINGFUL_ALPHA_MIN_RATIO = 0.01
MEANINGFUL_DARK_PIXEL_THRESHOLD = 175
MEANINGFUL_MIN_DARK_RATIO_DEFAULT = 0.012

BOX_NEEDLE_ASPECT_MIN = 0.35
BOX_NEEDLE_ASPECT_MAX = 7.0
BOX_IDEAL_ASPECT = 1.8
BOX_SCALE_SIDE_THRESHOLD = 2500
BOX_SCALE_COORD_MAX = 1300
BOX_SCALE_AREA_GAIN_THRESHOLD = 1.2


def _is_heic(content_type: str, filename: str) -> bool:
    type_value = (content_type or "").lower()
    name_value = (filename or "").lower()
    return (
        "heic" in type_value
        or "heif" in type_value
        or name_value.endswith(".heic")
        or name_value.endswith(".heif")
    )


def _replace_ext(filename: str, new_ext: str) -> str:
    stem = Path(filename or "upload").stem or "upload"
    return f"{stem}{new_ext}"


def _encode_normalized_jpeg(image_bytes: bytes) -> bytes:
    """
    Decode -> apply EXIF orientation -> encode as JPEG.
    This keeps OCR/cropping coordinate space consistent.
    """
    with Image.open(BytesIO(image_bytes)) as img:
        normalized = ImageOps.exif_transpose(img)
        if normalized.mode != "RGB":
            normalized = normalized.convert("RGB")
        buffer = BytesIO()
        normalized.save(buffer, format="JPEG", quality=92)
        buffer.seek(0)
        return buffer.read()


def _convert_heic_with_sips(image_bytes: bytes) -> bytes:
    """
    Use macOS `sips` as a fallback converter for HEIC/HEIF.
    """
    with TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / "input.heic"
        output_path = Path(temp_dir) / "output.jpg"
        input_path.write_bytes(image_bytes)

        result = subprocess.run(
            ["sips", "-s", "format", "jpeg", str(input_path), "--out", str(output_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not output_path.exists():
            stderr_text = (result.stderr or "").strip()
            raise RuntimeError(stderr_text or "sips convert failed")

        converted = output_path.read_bytes()
        if not converted.startswith(b"\xff\xd8") or not converted.endswith(b"\xff\xd9"):
            raise RuntimeError("sips produced invalid JPEG output")
        return converted


def normalize_image_for_ocr(
    image_bytes: bytes,
    content_type: str,
    filename: str,
) -> tuple[bytes, str, str]:
    """
    Normalize upload image before OCR call.
    - Convert HEIC/HEIF to JPEG to satisfy upstream OCR provider.
    """
    safe_content_type = content_type or "image/png"
    safe_filename = filename or "upload.png"

    working_bytes = image_bytes

    if _is_heic(safe_content_type, safe_filename):
        # Try Pillow HEIF support first (if plugin installed).
        try:
            working_bytes = _encode_normalized_jpeg(image_bytes)
            logger.info("Converted HEIC image with Pillow for OCR")
            return working_bytes, "image/jpeg", _replace_ext(safe_filename, ".jpg")
        except Exception:
            logger.warning("Pillow HEIC conversion unavailable, fallback to sips")

        # Fallback for macOS local dev/runtime.
        try:
            working_bytes = _convert_heic_with_sips(image_bytes)
        except Exception as exc:
            logger.exception("Failed to convert HEIC image for OCR")
            raise RuntimeError(
                "HEIC/HEIF 图片无法识别，请先转成 JPG/PNG 后再上传。"
            ) from exc

    # Normalize orientation for all images to keep bbox coordinates stable.
    try:
        normalized_bytes = _encode_normalized_jpeg(working_bytes)
        return normalized_bytes, "image/jpeg", _replace_ext(safe_filename, ".jpg")
    except Exception:
        # For non-HEIC, keep original bytes as fallback.
        if _is_heic(safe_content_type, safe_filename):
            raise RuntimeError("HEIC/HEIF 图片转换失败，请先转成 JPG/PNG 后再上传。")
        logger.warning("Failed to normalize image orientation; using original upload bytes")
        return image_bytes, safe_content_type, safe_filename


def get_image_size(image_bytes: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(image_bytes)) as img:
        normalized = ImageOps.exif_transpose(img)
        return normalized.size


def _clamp_image_box(box: ImageBox, width: int, height: int) -> ImageBox:
    ymin = max(0, min(int(box.ymin), height))
    xmin = max(0, min(int(box.xmin), width))
    ymax = max(ymin, min(int(box.ymax), height))
    xmax = max(xmin, min(int(box.xmax), width))
    return ImageBox(ymin=ymin, xmin=xmin, ymax=ymax, xmax=xmax)


def _image_box_area(box: ImageBox) -> int:
    return max(0, box.ymax - box.ymin) * max(0, box.xmax - box.xmin)


def _save_png_bytes(image: Image.Image, max_size: Optional[tuple[int, int]] = (800, 800)) -> tuple[bytes, int, int]:
    output = image.copy()
    if max_size:
        output.thumbnail(max_size, Image.Resampling.LANCZOS)
    buffer = BytesIO()
    output.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.read(), output.width, output.height


def _remove_red_pen_marks(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    pixels = rgb.load()
    width, height = rgb.size

    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if (
                r >= RED_MARK_R_MIN
                and r >= int(g * RED_MARK_R_OVER_G)
                and r >= int(b * RED_MARK_R_OVER_B)
            ):
                # 红笔批注擦白，减少干扰图示阅读
                pixels[x, y] = (255, 255, 255)
    return rgb


def _flatten_background_to_white(image: Image.Image) -> Image.Image:
    """
    Normalize uneven paper background into near-white while preserving strokes.
    Useful for photos with gray/yellow shadows.
    """
    rgb = image.convert("RGB")
    width, height = rgb.size

    blur_radius = max(
        BG_FLATTEN_BLUR_RADIUS_MIN,
        int(min(width, height) * BG_FLATTEN_BLUR_RADIUS_RATIO),
    )
    bg = rgb.convert("L").filter(ImageFilter.GaussianBlur(radius=blur_radius))

    src = rgb.load()
    bg_px = bg.load()
    out = Image.new("RGB", (width, height))
    out_px = out.load()

    for y in range(height):
        for x in range(width):
            r, g, b = src[x, y]
            base = max(12, bg_px[x, y])
            gain = BG_FLATTEN_GAIN_TARGET / float(base)
            gain = max(BG_FLATTEN_GAIN_MIN, min(BG_FLATTEN_GAIN_MAX, gain))
            nr = min(255, int((r - 128) * gain + 128 + BG_FLATTEN_LIGHT_BOOST))
            ng = min(255, int((g - 128) * gain + 128 + BG_FLATTEN_LIGHT_BOOST))
            nb = min(255, int((b - 128) * gain + 128 + BG_FLATTEN_LIGHT_BOOST))
            out_px[x, y] = (max(0, nr), max(0, ng), max(0, nb))
    return out


def _composite_on_white(image: Image.Image) -> Image.Image:
    if image.mode != "RGBA":
        return image.convert("RGB")
    white = Image.new("RGBA", image.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, image).convert("RGB")


def _compute_otsu_threshold(gray: Image.Image) -> int:
    hist = gray.histogram()
    total = sum(hist)
    if total <= 0:
        return OTSU_DEFAULT_THRESHOLD

    sum_all = 0.0
    for i, count in enumerate(hist):
        sum_all += i * count

    sum_bg = 0.0
    weight_bg = 0
    best_variance = -1.0
    threshold = OTSU_DEFAULT_THRESHOLD

    for i, count in enumerate(hist):
        weight_bg += count
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break

        sum_bg += i * count
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_all - sum_bg) / weight_fg
        between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if between > best_variance:
            best_variance = between
            threshold = i
    return max(OTSU_MIN_THRESHOLD, min(OTSU_MAX_THRESHOLD, threshold))


def _extract_diagram_cutout(image: Image.Image) -> Image.Image:
    """
    在候选图示框中做前景提取并聚类，仅保留最可能的图示簇，输出透明 PNG。
    """
    gray = image.convert("L")
    width, height = gray.size
    img_area = max(1, width * height)

    threshold = _compute_otsu_threshold(gray)
    raw = gray.tobytes()
    binary = bytearray(1 if value < threshold else 0 for value in raw)
    visited = bytearray(len(binary))

    components = []
    min_component = max(
        DIAGRAM_COMPONENT_MIN_AREA_PIXELS,
        int(img_area * DIAGRAM_COMPONENT_MIN_AREA_RATIO),
    )

    def _neighbors(idx: int):
        y, x = divmod(idx, width)
        if x > 0:
            yield idx - 1
        if x + 1 < width:
            yield idx + 1
        if y > 0:
            yield idx - width
        if y + 1 < height:
            yield idx + width

    for idx, is_fg in enumerate(binary):
        if not is_fg or visited[idx]:
            continue
        stack = [idx]
        visited[idx] = 1
        pixels = []
        min_x = width
        max_x = 0
        min_y = height
        max_y = 0

        while stack:
            cur = stack.pop()
            cy, cx = divmod(cur, width)
            pixels.append(cur)
            if cx < min_x:
                min_x = cx
            if cx > max_x:
                max_x = cx
            if cy < min_y:
                min_y = cy
            if cy > max_y:
                max_y = cy
            for nxt in _neighbors(cur):
                if binary[nxt] and not visited[nxt]:
                    visited[nxt] = 1
                    stack.append(nxt)

        area = len(pixels)
        if area < min_component:
            continue
        box_w = max(1, max_x - min_x + 1)
        box_h = max(1, max_y - min_y + 1)
        density = area / (box_w * box_h)
        components.append(
            {
                "pixels": pixels,
                "area": area,
                "min_x": min_x,
                "max_x": max_x,
                "min_y": min_y,
                "max_y": max_y,
                "center_y": (min_y + max_y) / 2.0,
                "density": density,
            }
        )

    if not components:
        return image.convert("RGBA")

    # 过滤明显噪声组件
    filtered = []
    for comp in components:
        box_w = max(1, comp["max_x"] - comp["min_x"] + 1)
        box_h = max(1, comp["max_y"] - comp["min_y"] + 1)
        aspect = box_w / box_h
        if comp["density"] < DIAGRAM_COMPONENT_DENSITY_MIN:
            continue
        if aspect > DIAGRAM_COMPONENT_ASPECT_MAX or aspect < DIAGRAM_COMPONENT_ASPECT_MIN:
            continue
        filtered.append(comp)
    if not filtered:
        filtered = components

    # 按 bbox 接近关系聚类，优先取面积更大且位置更靠上的簇
    n = len(filtered)
    visited_cluster = [False] * n
    pad_x = max(DIAGRAM_CLUSTER_GAP_X_MIN, int(width * DIAGRAM_CLUSTER_GAP_X_RATIO))
    pad_y = max(DIAGRAM_CLUSTER_GAP_Y_MIN, int(height * DIAGRAM_CLUSTER_GAP_Y_RATIO))

    def _is_near(a: dict, b: dict) -> bool:
        return not (
            a["max_x"] + pad_x < b["min_x"]
            or b["max_x"] + pad_x < a["min_x"]
            or a["max_y"] + pad_y < b["min_y"]
            or b["max_y"] + pad_y < a["min_y"]
        )

    best_cluster = None
    best_score = -1.0
    for i in range(n):
        if visited_cluster[i]:
            continue
        queue = [i]
        visited_cluster[i] = True
        indices = []
        while queue:
            cur = queue.pop()
            indices.append(cur)
            for j in range(n):
                if visited_cluster[j]:
                    continue
                if _is_near(filtered[cur], filtered[j]):
                    visited_cluster[j] = True
                    queue.append(j)

        cluster_area = sum(filtered[idx]["area"] for idx in indices)
        min_y = min(filtered[idx]["min_y"] for idx in indices)
        max_y = max(filtered[idx]["max_y"] for idx in indices)
        min_x = min(filtered[idx]["min_x"] for idx in indices)
        max_x = max(filtered[idx]["max_x"] for idx in indices)
        cluster_h = max(1, max_y - min_y + 1)
        cluster_w = max(1, max_x - min_x + 1)
        compactness = cluster_area / max(1, cluster_w * cluster_h)
        center_y = (min_y + max_y) / 2.0
        upper_bias = (
            DIAGRAM_CLUSTER_UPPER_BIAS_FACTOR
            if center_y <= height * DIAGRAM_CLUSTER_UPPER_BIAS_Y_RATIO
            else 1.0
        )
        score = cluster_area * compactness * upper_bias
        if score > best_score:
            best_score = score
            best_cluster = indices

    if not best_cluster:
        return image.convert("RGBA")

    alpha = Image.new("L", (width, height), 0)
    alpha_px = alpha.load()
    for idx in best_cluster:
        for p in filtered[idx]["pixels"]:
            py, px = divmod(p, width)
            alpha_px[px, py] = 255

    # 轻微膨胀，避免线条被切断
    alpha = alpha.filter(ImageFilter.MaxFilter(DIAGRAM_ALPHA_DILATE_SIZE))
    bbox = alpha.getbbox()
    if not bbox:
        return image.convert("RGBA")

    # 裁掉透明边缘，同时留出适度安全边距，避免主体被切太紧。
    pad_x = max(DIAGRAM_CUTOUT_PAD_X_MIN, int(width * DIAGRAM_CUTOUT_PAD_X_RATIO))
    pad_y = max(DIAGRAM_CUTOUT_PAD_Y_MIN, int(height * DIAGRAM_CUTOUT_PAD_Y_RATIO))
    left = max(0, bbox[0] - pad_x)
    top = max(0, bbox[1] - pad_y)
    right = min(width, bbox[2] + pad_x)
    bottom = min(height, bbox[3] + pad_y)
    alpha = alpha.crop((left, top, right, bottom))
    rgb = image.convert("RGBA").crop((left, top, right, bottom))
    rgb.putalpha(alpha)
    return rgb


def _find_foreground_segment(
    profile: list[float],
    gap: int = 6,
    prefer_top: bool = False,
) -> Optional[tuple[int, int]]:
    if not profile:
        return None
    max_value = max(profile)
    if max_value < FOREGROUND_PROFILE_MIN_PEAK:
        return None

    threshold = max(
        FOREGROUND_PROFILE_BASE_THRESHOLD,
        max_value * FOREGROUND_PROFILE_PEAK_THRESHOLD_RATIO,
    )
    segments: list[tuple[int, int, float]] = []
    start = None
    score = 0.0

    for idx, value in enumerate(profile):
        if value >= threshold:
            if start is None:
                start = idx
                score = value
            else:
                score += value
        else:
            if start is not None:
                segments.append((start, idx - 1, score))
                start = None
                score = 0.0
    if start is not None:
        segments.append((start, len(profile) - 1, score))

    if not segments:
        return None

    merged: list[tuple[int, int, float]] = []
    for seg in segments:
        if not merged:
            merged.append(seg)
            continue
        prev_start, prev_end, prev_score = merged[-1]
        cur_start, cur_end, cur_score = seg
        if cur_start - prev_end <= gap:
            merged[-1] = (prev_start, cur_end, prev_score + cur_score)
        else:
            merged.append(seg)

    if prefer_top:
        min_len = max(
            FOREGROUND_PREFER_TOP_MIN_LEN_PIXELS,
            int(len(profile) * FOREGROUND_PREFER_TOP_MIN_LEN_RATIO),
        )
        for start_idx, end_idx, _ in merged:
            if (end_idx - start_idx + 1) >= min_len:
                return (start_idx, end_idx)

    best = None
    best_score = -1.0
    total_len = float(len(profile))
    for start_idx, end_idx, seg_score in merged:
        seg_len = max(1, end_idx - start_idx + 1)
        density = seg_score / seg_len
        center = (start_idx + end_idx) / 2.0
        upper_bias = (
            FOREGROUND_UPPER_BIAS_FACTOR
            if center <= total_len * FOREGROUND_UPPER_BIAS_Y_RATIO
            else 1.0
        )
        length_weight = seg_len ** FOREGROUND_SEGMENT_LENGTH_WEIGHT_POWER
        # 使用“密度主导+长度弱加权”，避免整段文本全选。
        final_score = density * length_weight * upper_bias
        if final_score > best_score:
            best_score = final_score
            best = (start_idx, end_idx)
    return best


def _tighten_to_foreground(
    image: Image.Image,
    *,
    prefer_top: bool = True,
    trim_bottom_on_tall: bool = True,
) -> Image.Image:
    gray = image.convert("L")
    width, height = gray.size
    pixels = gray.load()

    row_profile = []
    for y in range(height):
        dark = 0
        for x in range(width):
            if pixels[x, y] < FOREGROUND_DARK_PIXEL_THRESHOLD:
                dark += 1
        row_profile.append(dark / max(1, width))

    col_profile = []
    for x in range(width):
        dark = 0
        for y in range(height):
            if pixels[x, y] < FOREGROUND_DARK_PIXEL_THRESHOLD:
                dark += 1
        col_profile.append(dark / max(1, height))

    row_seg = _find_foreground_segment(row_profile, gap=3, prefer_top=prefer_top)
    col_seg = _find_foreground_segment(col_profile, gap=4)
    if not row_seg or not col_seg:
        return image

    y1, y2 = row_seg
    x1, x2 = col_seg
    if y2 <= y1 or x2 <= x1:
        return image

    # 若行分割仍过高，进一步砍掉下半部，降低手写答案干扰。
    if trim_bottom_on_tall and (y2 - y1 + 1) >= int(height * FOREGROUND_MAX_HEIGHT_RATIO):
        y2 = max(y1 + 1, int(height * FOREGROUND_TRIM_HEIGHT_RATIO))

    pad_y = max(FOREGROUND_PAD_MIN, int((y2 - y1 + 1) * FOREGROUND_PAD_RATIO))
    pad_x = max(FOREGROUND_PAD_MIN, int((x2 - x1 + 1) * FOREGROUND_PAD_RATIO))
    top = max(0, y1 - pad_y)
    left = max(0, x1 - pad_x)
    bottom = min(height, y2 + pad_y + 1)
    right = min(width, x2 + pad_x + 1)

    original_area = width * height
    new_area = max(1, (right - left) * (bottom - top))
    # 防止过度裁切
    if new_area < original_area * FOREGROUND_MIN_AREA_RATIO:
        return image

    return image.crop((left, top, right, bottom))


def has_meaningful_content(
    image_bytes: bytes,
    min_dark_ratio: float = MEANINGFUL_MIN_DARK_RATIO_DEFAULT,
) -> bool:
    """
    粗略判断裁剪结果是否包含有效图形内容，避免空白图被当作图示。
    """
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            if "A" in img.getbands():
                alpha = img.getchannel("A")
                non_transparent = sum(1 for value in alpha.getdata() if value > 0)
                total = max(1, img.width * img.height)
                if non_transparent / total < MEANINGFUL_ALPHA_MIN_RATIO:
                    return False
            gray = img.convert("L")
            pixels = gray.load()
            width, height = gray.size
            dark = 0
            total = max(1, width * height)
            for y in range(height):
                for x in range(width):
                    if pixels[x, y] < MEANINGFUL_DARK_PIXEL_THRESHOLD:
                        dark += 1
            return (dark / total) >= min_dark_ratio
    except Exception:
        return True


def normalize_image_box_for_source(
    box: Optional[ImageBox],
    image_width: int,
    image_height: int,
) -> Optional[ImageBox]:
    """
    Normalize model bbox into image pixel coordinates.
    Handles:
    - swapped list order ([xmin,ymin,xmax,ymax] vs [ymin,xmin,ymax,xmax])
    - large image + model 0~1000 coordinate space
    """
    if not box:
        return None

    as_is = box
    swapped = ImageBox(
        ymin=box.xmin,
        xmin=box.ymin,
        ymax=box.xmax,
        xmax=box.ymax,
    )

    def score(candidate: ImageBox) -> tuple[int, int, int, float]:
        overflow = (
            max(0, int(candidate.xmin) - image_width)
            + max(0, int(candidate.xmax) - image_width)
            + max(0, int(candidate.ymin) - image_height)
            + max(0, int(candidate.ymax) - image_height)
        )
        clamped = _clamp_image_box(candidate, image_width, image_height)
        width = max(1, int(clamped.xmax) - int(clamped.xmin))
        height = max(1, int(clamped.ymax) - int(clamped.ymin))
        aspect = width / height
        # 极细长框通常是坐标轴取反后的结果，给出惩罚。
        needle_penalty = 1 if (aspect < BOX_NEEDLE_ASPECT_MIN or aspect > BOX_NEEDLE_ASPECT_MAX) else 0
        # 题目/图示多数是横排内容，宽高比更接近 1~4 的候选框更可信。
        ratio_distance = abs(aspect - BOX_IDEAL_ASPECT)
        return overflow, -_image_box_area(clamped), needle_penalty, ratio_distance

    chosen = min((as_is, swapped), key=score)

    # If bbox coords look like 0~1000 scale, map to real pixels.
    chosen_overflow = score(chosen)[0]
    max_coord = max(int(chosen.xmax), int(chosen.ymax))
    should_try_scale = (
        (max(image_width, image_height) >= BOX_SCALE_SIDE_THRESHOLD and max_coord <= BOX_SCALE_COORD_MAX)
        or (chosen_overflow > 0 and max_coord <= BOX_SCALE_COORD_MAX)
    )
    if should_try_scale:
        scaled = ImageBox(
            ymin=round(chosen.ymin * image_height / 1000),
            xmin=round(chosen.xmin * image_width / 1000),
            ymax=round(chosen.ymax * image_height / 1000),
            xmax=round(chosen.xmax * image_width / 1000),
        )
        scaled_clamped = _clamp_image_box(scaled, image_width, image_height)
        chosen_clamped = _clamp_image_box(chosen, image_width, image_height)
        scaled_overflow = score(scaled)[0]
        if (
            scaled_overflow < chosen_overflow
            or _image_box_area(scaled_clamped)
            > _image_box_area(chosen_clamped) * BOX_SCALE_AREA_GAIN_THRESHOLD
        ):
            chosen = scaled

    return _clamp_image_box(chosen, image_width, image_height)


def crop_diagram_image(
    image_bytes: bytes,
    ymin: int,
    xmin: int,
    ymax: int,
    xmax: int,
    max_size: Optional[tuple[int, int]] = (800, 800),
) -> tuple[bytes, int, int]:
    """
    针对题内图示的裁剪：
    - 先按 image_box 粗裁
    - 尝试去掉红色批注
    - 按前景密度自动收紧，尽量避开手写答案区
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img)
        width, height = img.size

        ymin = max(0, min(ymin, height))
        xmin = max(0, min(xmin, width))
        ymax = max(ymin, min(ymax, height))
        xmax = max(xmin, min(xmax, width))
        if ymax <= ymin or xmax <= xmin:
            raise ValueError("Invalid crop coordinates")

        cropped = img.crop((xmin, ymin, xmax, ymax))
        cleaned = _remove_red_pen_marks(cropped)
        normalized = _flatten_background_to_white(cleaned)
        # Diagram may appear in the lower half; avoid top-biased trimming here.
        tightened = _tighten_to_foreground(
            normalized,
            prefer_top=False,
            trim_bottom_on_tall=False,
        )
        cutout = _extract_diagram_cutout(tightened)

        source_area = max(1, tightened.width * tightened.height)
        cutout_area = max(1, cutout.width * cutout.height)
        # 若抠图相对候选框过小，回退到放宽版，避免图示主体被截得太少。
        if cutout_area / source_area < DIAGRAM_CUTOUT_MIN_AREA_RATIO:
            cutout = tightened.convert("RGBA")

        # Export white background output so users can use it directly in cards/PDF.
        final_image = _composite_on_white(cutout)
        result_bytes, out_w, out_h = _save_png_bytes(final_image, max_size=max_size)

        logger.info(
            "Cropped diagram image: (%d,%d,%d,%d) -> %dx%d",
            ymin,
            xmin,
            ymax,
            xmax,
            out_w,
            out_h,
        )
        return result_bytes, out_w, out_h
    except ValueError:
        raise
    except Exception as exc:
        logger.exception("Diagram crop failed")
        raise RuntimeError(f"Diagram crop failed: {str(exc)}") from exc


def crop_image(
    image_bytes: bytes,
    ymin: int,
    xmin: int,
    ymax: int,
    xmax: int,
    max_size: Optional[tuple[int, int]] = (800, 800)
) -> tuple[bytes, int, int]:
    """
    裁剪图片并返回裁剪后的字节流。

    Args:
        image_bytes: 原始图片字节流
        ymin, xmin, ymax, xmax: 裁剪坐标（原始图片坐标系）
        max_size: 最大尺寸限制（宽，高），None 表示不限制

    Returns:
        (cropped_bytes, width, height): 裁剪后的图片字节流和尺寸

    Raises:
        ValueError: 坐标无效
        RuntimeError: 图片处理失败
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img)
        width, height = img.size

        # 坐标校验（防止越界）
        ymin = max(0, min(ymin, height))
        xmin = max(0, min(xmin, width))
        ymax = max(ymin, min(ymax, height))
        xmax = max(xmin, min(xmax, width))

        # 检查裁剪区域是否有效
        if ymax <= ymin or xmax <= xmin:
            logger.error(
                "Invalid crop box: (%d,%d,%d,%d) for image size (%d,%d)",
                ymin, xmin, ymax, xmax, width, height
            )
            raise ValueError("Invalid crop coordinates")

        # PIL 使用 (left, upper, right, lower) = (xmin, ymin, xmax, ymax)
        cropped = img.crop((xmin, ymin, xmax, ymax))
        cropped_bytes, out_w, out_h = _save_png_bytes(cropped, max_size=max_size)

        logger.info(
            "Cropped image: (%d,%d,%d,%d) -> %dx%d",
            ymin, xmin, ymax, xmax,
            out_w, out_h
        )

        return cropped_bytes, out_w, out_h

    except ValueError:
        raise
    except Exception as e:
        logger.exception("Image crop failed")
        raise RuntimeError(f"Image crop failed: {str(e)}") from e
