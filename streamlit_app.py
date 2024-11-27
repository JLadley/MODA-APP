import streamlit as st
from PyPDF2 import PdfReader
import openai
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    st.error("OpenAI API Key not found. Please add it to the .env file.")
    st.stop()

# AI-Based Scoring Function
def calculate_moda_score_with_ai(fields, weights):
    scores = {}
    explanations = {}

    for criterion, weight in weights.items():
        prompt = f"""
        Analyze the following project details and assign a score (0-100) for the criterion '{criterion}':
        - Need Description: {fields.get('Need Description', 'No Data')}
        - Expected Outcomes: {fields.get('Expected Outcomes', 'No Data')}
        - Strategic Fit: {fields.get('Strategic Fit', 'No Data')}

        Respond in this structured format:
        Score: [number]
        Reasoning: [Provide a detailed explanation, including specific references to project data and alignment with the criterion.]
        """
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert in project prioritization and evaluation."},
                    {"role": "user", "content": prompt}
                ]
            )
            output = response['choices'][0]['message']['content'].strip()

            # Parse response for score and reasoning
            score_line = next((line for line in output.split("\n") if line.startswith("Score:")), None)
            reasoning_line = next((line for line in output.split("\n") if line.startswith("Reasoning:")), None)

            scores[criterion] = int(score_line.replace("Score:", "").strip()) if score_line else 0
            explanations[criterion] = reasoning_line.replace("Reasoning:", "").strip() if reasoning_line else "No reasoning provided."
        except Exception as e:
            scores[criterion] = 0
            explanations[criterion] = f"Error: {str(e)}"

    # Calculate total weighted score
    weighted_scores = {}
    total_score = 0
    for criterion, raw_score in scores.items():
        weighted_score = (raw_score * weights[criterion]) / 100
        weighted_scores[criterion] = weighted_score
        total_score += weighted_score

    return total_score, weighted_scores, explanations

# Project Selection Logic
def allocate_funding(projects, budget, strategy="highest_score"):
    selected_projects = []
    excluded_projects = []
    remaining_budget = budget

    if strategy == "highest_score":
        projects = sorted(projects, key=lambda x: x['score'], reverse=True)

    for project in projects:
        if project['cost'] <= remaining_budget:
            selected_projects.append(project)
            remaining_budget -= project['cost']
        else:
            excluded_projects.append(project)

    return selected_projects, excluded_projects, remaining_budget

# App Title
st.title("MODA App - Project Prioritization Tool")

# Sidebar for Weight Adjustment Sliders
with st.sidebar:
    st.header("Adjust Criteria Weights")
    weights = {
        "Community Impact": st.slider("Community Impact Weight (%)", 0, 100, 10),
        "Operational Efficiency": st.slider("Operational Efficiency Weight (%)", 0, 100, 10),
        "Longevity": st.slider("Longevity Weight (%)", 0, 100, 15),
        "Public Safety": st.slider("Public Safety Weight (%)", 0, 100, 20),
        "Service Delivery": st.slider("Service Delivery Weight (%)", 0, 100, 15),
        "Cost Efficiency": st.slider("Cost Efficiency Weight (%)", 0, 100, 15),
        "Regulatory Compliance": st.slider("Regulatory Compliance Weight (%)", 0, 100, 15),
        "State of Good Repair": st.slider("State of Good Repair Weight (%)", 0, 100, 10),
    }

    total_weight = sum(weights.values())
    st.write(f"**Total Weight: {total_weight}%**")
    if total_weight != 100:
        st.error("Weights must total 100%! Adjust the sliders.")
        st.stop()

    st.header("Set Funding Limit")
    budget = st.number_input("Enter total available funding ($):", min_value=0, value=500000)

# PDF Upload
st.subheader("Upload Project PDFs")
uploaded_pdfs = st.file_uploader("Upload fillable PDF files", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    projects = []
    for uploaded_pdf in uploaded_pdfs:
        reader = PdfReader(uploaded_pdf)
        fields = {}
        if "/AcroForm" in reader.trailer["/Root"] and "/Fields" in reader.trailer["/Root"]["/AcroForm"]:
            for field in reader.trailer["/Root"]["/AcroForm"]["/Fields"]:
                field_object = field.get_object()
                field_name = field_object.get("/T", "Unnamed Field")
                field_value = field_object.get("/V", "No Value")
                fields[field_name] = field_value

        # Calculate MODA Score
        total_score, weighted_scores, explanations = calculate_moda_score_with_ai(fields, weights)
        project_details = {
            "name": fields.get("Project Name", f"Unnamed Project ({uploaded_pdf.name})"),
            "cost": float(fields.get("Grand Total", 0)),
            "score": total_score,
            "details": fields,
            "explanations": explanations,
        }
        projects.append(project_details)

    # Funding Allocation
    selected_projects, excluded_projects, remaining_budget = allocate_funding(projects, budget)

    st.write("## Funding Allocation Results")
    st.write("### Selected Projects")
    for project in selected_projects:
        st.write(f"- **{project['name']} (${project['cost']:.2f}):** Score: {project['score']:.2f}")

    st.write("### Excluded Projects")
    for project in excluded_projects:
        st.write(f"- **{project['name']} (${project['cost']:.2f}):** Score: {project['score']:.2f}")

    st.write(f"**Remaining Budget:** ${remaining_budget:.2f}")

    # Justification for Decisions
    st.write("## Funding Rationale")
    for project in selected_projects:
        st.write(f"**{project['name']}**")
        for criterion, explanation in project["explanations"].items():
            st.write(f"- **{criterion}:** {explanation}")

