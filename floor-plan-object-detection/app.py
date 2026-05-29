import streamlit as st
from ultralytics import YOLO
import PIL
import helper
import setting

def main():
    """
    Main function for the Streamlit app.
    """
    setting.configure_page()

    # Creating sidebar
    with st.sidebar:
        st.header("Image Configuration")     # Adding header to sidebar
        # Adding file uploader to sidebar for selecting images
        source_img = st.sidebar.file_uploader(
            "Choose an image...", type=("jpg", "jpeg", "png"))

        # Model Options
        confidence = setting.get_model_confidence()

        # Multiselect for selecting labels
        available_labels = ['Column', 'Curtain Wall', 'Dimension', 'Door', 'Railing', 'Sliding Door', 'Stair Case', 'Wall', 'Window']
        selected_labels = setting.select_labels(available_labels)

    # Creating main page heading
    st.title("Floor Plan Object Detection using YOLOv8")

    # Creating two columns on the main page
    col1, col2 = st.columns(2)

    # Adding image to the first column if image is uploaded
    with col1:
        if source_img:
            # Opening the uploaded image
            uploaded_image = PIL.Image.open(source_img)
            # Adding the uploaded image to the page with a caption
            st.image(source_img,caption="Uploaded Image",use_column_width=True)
        else:
            st.warning("Please upload an image.")

    model = YOLO('best.pt')

    if st.sidebar.button('Detect Objects'):
        if not source_img:
            st.warning("Please upload an image before detecting objects.")
        else:
            res = model.predict(uploaded_image, conf=confidence)

            filtered_boxes = [
                box for box in res[0].boxes
                if model.names[int(box.cls)] in selected_labels
            ]

            res[0].boxes = filtered_boxes
            res_plotted = res[0].plot()[:, :, ::-1]

            # ---------------------------------
            # NEW CODE STARTS HERE
            # ---------------------------------

            import pandas as pd

            door_data = []

            for box in filtered_boxes:
                label = model.names[int(box.cls)]

                if label == "Door":
                    x1, y1, x2, y2 = box.xyxy[0].tolist()

                    door_data.append({
                        "label": label,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                        "center_x": (x1 + x2) / 2,
                        "center_y": (y1 + y2) / 2
                    })

            door_df = pd.DataFrame(door_data)

            csv = door_df.to_csv(index=False).encode('utf-8')

            # ---------------------------------
            # DISPLAY RESULTS
            # ---------------------------------

            with col2:
                st.image(
                    res_plotted,
                    caption='Detected Image',
                    use_column_width=True
                )

                st.write("Detected Doors and Locations")
                st.dataframe(door_df)

                st.download_button(
                    label="Download Door Locations CSV",
                    data=csv,
                    file_name='door_locations.csv',
                    mime='text/csv'
                )

if __name__ == "__main__":
    main()
