import io
import os
from datetime import datetime

import piexif
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ExifTags
import pyheif

st.set_page_config(page_title="Simple Image Editor", layout="wide")

@st.cache_data()
def convert_heic_to_jpeg(image_file: io.BytesIO) -> Image.Image:
    """
    Convert a HEIC image to JPEG in-memory using pyheif for decoding,
    then return a PIL Image object. EXIF data (if present) is extracted,
    optionally modified, and re-embedded.
    """

    # Decode the HEIC file using pyheif
    try:
        heif_data = pyheif.read_heif(image_file.getvalue())
    except Exception as e:
        st.warning(f"Could not read HEIC file: {e}")
        return None

    # Convert the raw HEIF data to a PIL Image
    image = Image.frombytes(
        heif_data.mode,
        heif_data.size,
        heif_data.data,
        "raw",
        heif_data.mode,
        0,
        1,
    )

    # Attempt to locate and parse EXIF within metadata blocks
    exif_bytes = None
    if heif_data.metadata:
        for meta_block in heif_data.metadata:
            if meta_block["type"] == "Exif":
                raw_exif = meta_block["data"]

                try:
                    exif_dict = piexif.load(raw_exif)

                    # -------------------------
                    # Example: parse DateTime
                    # -------------------------
                    date_str = None
                    if piexif.ImageIFD.DateTime in exif_dict["0th"]:
                        dt_bytes = exif_dict["0th"][piexif.ImageIFD.DateTime]
                        date_str = (
                            dt_bytes.decode("utf-8") if isinstance(dt_bytes, bytes) else dt_bytes
                        )

                    if date_str:
                        try:
                            date_obj = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                            exif_dict["0th"][piexif.ImageIFD.Orientation] = 1
                            exif_dict["0th"][piexif.ImageIFD.DateTime] = date_obj.strftime(
                                "%Y:%m:%d %H:%M:%S"
                            )
                        except ValueError:
                            pass

                    exif_bytes = piexif.dump(exif_dict)

                except Exception as exif_error:
                    st.warning(f"Error parsing EXIF metadata: {exif_error}")
                break

    # Now convert to JPEG in memory, embedding EXIF if available
    output = io.BytesIO()
    try:
        if exif_bytes:
            image.save(output, format="JPEG", exif=exif_bytes)
        else:
            image.save(output, format="JPEG")
    except Exception as e:
        st.warning(f"Could not save JPEG: {e}")
        return None

    output.seek(0)
    return Image.open(output)

def main():
    # File uploader (including HEIC)
    if not st.session_state.get('image_upload'):
        uploaded_file = st.file_uploader(
            "Upload an Image", type=["png", "jpg", "jpeg", "webp", "heic", "heif"], key='image_upload'
        )
        if uploaded_file is not None:
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()
            if file_extension in [".heic", ".heif"]:
                st.info("Detected HEIC/HEIF image. Converting to JPEG in memory...")
    else:
        with st.expander('uploaded_file'):
            uploaded_file = st.file_uploader(
                "Upload an Image", type=["png", "jpg", "jpeg", "webp", "heic", "heif"], key='image_upload'
            )
            if uploaded_file is not None:
                file_extension = os.path.splitext(uploaded_file.name)[1].lower()
                if file_extension in [".heic", ".heif"]:
                    st.info("Detected HEIC/HEIF image. Converting to JPEG in memory...")

    if uploaded_file is not None:
        # Check extension to see if we need to convert from HEIC to JPEG
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()

        if file_extension in [".heic", ".heif"]:
            image = convert_heic_to_jpeg(uploaded_file)
        else:
            image = Image.open(uploaded_file)

        c1, c2 = st.columns((1, 2))

        with c1:
            # Show basic EXIF if available
            exif_data = image.getexif()
            if exif_data:
                with st.popover("EXIF Data", use_container_width=True):
                    exif_dict = {}
                    for tag_id, value in exif_data.items():
                        tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                        exif_dict[tag_name] = value
                    st.json(exif_dict)
            else:
                st.caption("No EXIF data found.")

        # Prepare placeholders for metrics
        with c1.container():
            resolution_placeholder = st.empty()
            color_mode_placeholder = st.empty()
            file_size_placeholder = st.empty()
            dpi_placeholder = st.empty()

        # Possibly read DPI from image info
        dpi = image.info.get("dpi")

        with st.sidebar:
            # *** Rotation ***
            st.subheader("Rotation")
            rotation_degrees = (
                st.pills(
                    "Rotate image",
                    (90, 180, 270, "other"),
                    label_visibility="collapsed",
                )
                or 0
            )
            if rotation_degrees == "other":
                rotation_degrees = st.slider("how much?", 0, 359, 0, 1)

            if rotation_degrees != 0:
                image = image.rotate(rotation_degrees, expand=True)

            # Scaling
            st.subheader("Scaling")
            scale_percent = (
                st.pills(
                    "Scale image (%)",
                    (25, 50, 75, 150, 200, "other"),
                    label_visibility="collapsed",
                )
                or 100
            )
            if scale_percent == "other":
                scale_percent = st.slider("Enter custom scale (%)", 1, 1000, 100, 1)
            if scale_percent != 100:
                orig_w, orig_h = image.size
                new_w = int(orig_w * scale_percent / 100)
                new_h = int(orig_h * scale_percent / 100)
                image = image.resize((new_w, new_h))

            st.subheader("Basic Image Enhancements")

            # Brightness
            brightness_factor = st.slider("Brightness", 0.0, 2.0, 1.0, 0.1)
            if brightness_factor != 1.0:
                enhancer = ImageEnhance.Brightness(image)
                image = enhancer.enhance(brightness_factor)

            # Contrast
            contrast_factor = st.slider("Contrast", 0.0, 2.0, 1.0, 0.1)
            if contrast_factor != 1.0:
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(contrast_factor)

            # Sharpness
            sharpness_factor = st.slider("Sharpness", 0.0, 2.0, 1.0, 0.1)
            if sharpness_factor != 1.0:
                enhancer = ImageEnhance.Sharpness(image)
                image = enhancer.enhance(sharpness_factor)

            # Color / Saturation
            color_factor = st.slider("Color / Saturation", 0.0, 2.0, 1.0, 0.1)
            if color_factor != 1.0:
                enhancer = ImageEnhance.Color(image)
                image = enhancer.enhance(color_factor)

            st.subheader("Advanced Filters & Effects")

            # Gaussian Blur
            blur_check = st.toggle("Apply Gaussian Blur")
            if blur_check:
                blur_radius = st.slider("Blur Radius", 0.0, 10.0, 2.0, 0.5)
                image = image.filter(ImageFilter.GaussianBlur(blur_radius))

            # Edge Detection
            edge_check = st.toggle("Apply Edge Detection")
            if edge_check:
                image = image.filter(ImageFilter.FIND_EDGES)

            # Invert
            invert_check = st.toggle("Invert Colors")
            if invert_check:
                if image.mode != "RGB":
                    image = image.convert("RGB")
                image = ImageOps.invert(image)

            # Grayscale
            grayscale_check = st.toggle("Grayscale")
            if grayscale_check:
                image = ImageOps.grayscale(image)

            # Posterize
            posterize_check = st.toggle("Posterize")
            if posterize_check:
                bits = st.slider("Posterize Bits (1=most extreme, 8=subtle)", 1, 8, 4, 1)
                image = ImageOps.posterize(image, bits)

            # Solarize
            solarize_check = st.toggle("Solarize")
            if solarize_check:
                threshold = st.slider("Solarize Threshold", 0, 255, 128, 1)
                image = ImageOps.solarize(image, threshold=threshold)

            st.subheader('Other')
            apply_exif_transpose = st.toggle("Apply EXIF Transpose", True)
            if apply_exif_transpose:
                image = ImageOps.exif_transpose(image)

        # Update placeholders with final info
        resolution_placeholder.metric("Resolution", f"{image.width} x {image.height}")
        color_mode_placeholder.metric("Color Mode", image.mode)
        if dpi:
            dpi_placeholder.metric("DPI", f"{dpi}")
        else:
            dpi_placeholder.metric("DPI", "N/A")

        with c2:
            st.image(image, use_container_width=False)

        inner_c1, inner_c2, *_ = c2.columns((2))
        file_format = inner_c1.selectbox(
            "Output format", ["PNG", "JPEG", "WEBP"],  # PNG as default
            index=0,
            label_visibility="collapsed"
        )
        download_button = inner_c2.button(":material/download:")

        if download_button:
            # Convert final image to bytes
            with io.BytesIO() as output:
                image.save(output, format=file_format)
                processed_image_bytes = output.getvalue()

            processed_size = len(processed_image_bytes)
            processed_size_mb = processed_size / (1024 * 1024)
            st.download_button(
                label=f"Download ({processed_size_mb:.2f} MB)",
                data=processed_image_bytes,
                file_name=f"processed_image.{file_format.lower()}",
                mime=f"image/{file_format.lower()}",
                use_container_width=True,
                type="primary",
            )
            st.image(processed_image_bytes)

if __name__ == "__main__":
    main()
