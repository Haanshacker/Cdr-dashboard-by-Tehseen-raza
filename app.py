import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64

# Page config
st.set_page_config(page_title="CDR Dashboard by Tehseen Raza", layout="wide")

# Header
st.markdown("""
    <style>
        .title {
            font-size:40px;
            font-weight:bold;
            color:#2c3e50;
            text-align:center;
        }
        .subtitle {
            font-size:20px;
            color:#7f8c8d;
            text-align:center;
        }
    </style>
    <div class="title">📊 CDR Dashboard</div>
    <div class="subtitle">by Tehseen Razzaq</div>
""", unsafe_allow_html=True)

# File uploader
uploaded_file = st.file_uploader("📁 Upload your CDR file", type=["csv", "xlsx", "xls"])

if uploaded_file:
    try:
        # Read file
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.success("✅ File uploaded successfully!")

        # Show preview
        st.subheader("📄 File Preview")
        st.dataframe(df)

        # Show basic stats
        st.subheader("📊 File Summary")
        st.write(f"**Total Rows:** {df.shape[0]}")
        st.write(f"**Total Columns:** {df.shape[1]}")
        st.write("**Column Names:**")
        st.code(", ".join(df.columns))

        # Optional: show nulls
        st.write("**Missing Values per Column:**")
        st.dataframe(df.isnull().sum())

        # PDF Export
        def create_pdf(dataframe):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=10)
            pdf.cell(200, 10, txt="CDR Summary - Dashboard by Tehseen Razzaq", ln=True, align='C')
            pdf.ln(10)
            pdf.cell(200, 10, txt=f"Total Rows: {dataframe.shape[0]}", ln=True)
            pdf.cell(200, 10, txt=f"Total Columns: {dataframe.shape[1]}", ln=True)
            pdf.cell(200, 10, txt="Columns: " + ', '.join(dataframe.columns), ln=True)
            pdf.ln(10)
            for i, row in dataframe.iterrows():
                line = ', '.join(str(cell) for cell in row)
                pdf.multi_cell(0, 10, txt=line)
                if i >= 20: break  # Limit rows
            return pdf

        def download_pdf(pdf):
            pdf.output("report.pdf")
            with open("report.pdf", "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
            href = f'<a href="data:application/pdf;base64,{base64_pdf}" download="CDR_Report_Tehseen.pdf">📥 Download PDF Report</a>'
            st.markdown(href, unsafe_allow_html=True)

        st.subheader("📤 Export Analysis to PDF")
        pdf = create_pdf(df)
        download_pdf(pdf)

    except Exception as e:
        st.error(f"❌ Error reading file: {e}")
else:
    st.info("📌 Please upload a CDR file to begin.")
