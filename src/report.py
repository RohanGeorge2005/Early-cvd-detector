"""On-demand PDF report generation for the active hybrid assessment."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from src.patient_graph import patient_graph_data, render_patient_graph
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle, KeepTogether)


NAVY = colors.HexColor("#0B2438")
TEAL = colors.HexColor("#158A87")
MUTED = colors.HexColor("#586A78")
PALE = colors.HexColor("#EFF5F7")


def build_report(patient: dict, result: dict, metadata: dict, assessment_id: str | None = None,
                 assessed_at: str | None = None) -> bytes:
    # Build and validate the required patient-specific graphic before starting
    # the PDF, so a report is never returned without its matching graph.
    graph_data = patient_graph_data(patient, result)
    graph_image = BytesIO(render_patient_graph(patient, result))
    graph_image.seek(0)
    assessment_id = assessment_id or "On-demand assessment"
    if assessed_at:
        try:
            assessment_date = datetime.fromisoformat(assessed_at.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M %Z")
        except ValueError:
            assessment_date = assessed_at
    else:
        assessment_date = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=.62*inch, leftMargin=.62*inch,
                            topMargin=.62*inch, bottomMargin=.62*inch, title="Explainable AI Cardiovascular Risk Assessment",
                            author="XAI-CVD academic research prototype")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20,
                              leading=25, textColor=NAVY, alignment=TA_CENTER, spaceAfter=7))
    styles.add(ParagraphStyle(name="SubTitle", parent=styles["Normal"], fontSize=10, leading=14, textColor=MUTED,
                              alignment=TA_CENTER, spaceAfter=12))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=12.5, leading=16,
                              textColor=NAVY, spaceBefore=10, spaceAfter=6, keepWithNext=True))
    styles.add(ParagraphStyle(name="BodySmall", parent=styles["BodyText"], fontSize=8.7, leading=12, textColor=NAVY))
    styles.add(ParagraphStyle(name="Disclaimer", parent=styles["BodyText"], fontSize=9, leading=13,
                              textColor=NAVY, backColor=colors.HexColor("#FFF5DF"), borderColor=colors.HexColor("#D6A94D"),
                              borderWidth=.7, borderPadding=8, spaceBefore=6, spaceAfter=6))
    story = [Paragraph("EXPLAINABLE AI CARDIOVASCULAR RISK ASSESSMENT", styles["ReportTitle"]),
             Paragraph("AI-Assisted Risk Assessment and Decision Support", styles["SubTitle"]),
             Paragraph(f"Assessment {assessment_id} · assessed {assessment_date} · XAI-CVD research prototype", styles["SubTitle"])]
    category = result["risk_category"]
    category_color = {"LOW": colors.HexColor("#21845E"), "MODERATE": colors.HexColor("#AD7411"), "HIGH": colors.HexColor("#C3454A")}.get(category, TEAL)
    category_html = "#" + category_color.hexval()[-6:]
    risk_box = Table([[Paragraph("ESTIMATED 10-YEAR CHD RISK", styles["BodySmall"]),
                       Paragraph(f"<font size='23'><b>{result['probability']:.1%}</b></font><br/><font color='{category_html}'><b>{category} · model-based category</b></font>", styles["BodySmall"]),
                       Paragraph(f"{result['binary_label']}<br/>Hybrid ML + Deep Learning<br/>Tree branch: {result['tree_component']}", styles["BodySmall"])]], colWidths=[2.0*inch, 2.2*inch, 2.3*inch])
    risk_box.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,-1),PALE), ("BOX",(0,0),(-1,-1),.7,colors.HexColor("#D7E2E8")),
                                  ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),10),
                                  ("RIGHTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),12),
                                  ("BOTTOMPADDING",(0,0),(-1,-1),12)]))
    story += [risk_box, Spacer(1, 9)]
    def section(title): story.append(Paragraph(title, styles["Section"]))
    def table(data, widths=None):
        t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8.2),
            ("LEADING",(0,0),(-1,-1),11), ("GRID",(0,0),(-1,-1),.35,colors.HexColor("#D7E2E8")),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,PALE]), ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("LEFTPADDING",(0,0),(-1,-1),6), ("RIGHTPADDING",(0,0),(-1,-1),6),
            ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5)]))
        story.append(t)
    yesno = lambda v: "Yes" if v else "No"
    patient_rows = [
        ["Feature", "Entered value", "Feature", "Entered value"],
        ["Age", f"{patient['age']} years", "Gender", "Male" if patient["gender"] else "Female"],
        ["Education", str(patient["education"]), "Current smoker", yesno(patient["currentSmoker"])],
        ["Cigarettes/day", str(patient["cigsPerDay"]), "BP medication", yesno(patient["BPMeds"])],
        ["Previous stroke", yesno(patient["prevalentStroke"]), "Hypertension", yesno(patient["prevalentHyp"])],
        ["Diabetes", yesno(patient["diabetes"]), "Total cholesterol", f"{patient['totChol']:g} mg/dL"],
        ["Systolic BP", f"{patient['sysBP']:g} mmHg", "Diastolic BP", f"{patient['diaBP']:g} mmHg"],
        ["BMI", f"{patient['BMI']:g} kg/m²", "Resting heart rate", f"{patient['heartRate']:g} bpm"],
        ["Fasting glucose", f"{patient['glucose']:g} mg/dL", "", ""],
    ]
    section("1 · Patient assessment summary")
    table(patient_rows, [1.25*inch, 1.7*inch, 1.35*inch, 2.0*inch])
    section("2 · Hybrid risk assessment")
    story.append(Paragraph(f"Hybrid probability: <b>{result['probability']:.1%}</b> · model-based category: <b>{category}</b> · binary output: <b>{result['binary_label']}</b>. The hybrid combines the {result['tree_component']} probability with an MLP probability using a training-validation-calibrated weight α={result['alpha']:.2f}.", styles["BodySmall"]))
    section("3 · Model comparison · held-out evaluation")
    model_rows = [["Model", "ROC-AUC", "F1", "Recall", "Accuracy"]]
    for name, m in metadata["metrics"].items():
        model_rows.append([name, *[f"{m[k]:.3f}" for k in ("roc_auc", "f1", "recall", "accuracy")]])
    table(model_rows, [2.55*inch, .9*inch, .75*inch, .8*inch, 1.05*inch])
    section("4 · Model consensus")
    model_lines = [f"{name}: {value:.1%} · {'Higher' if value >= result['model_threshold'] else 'Lower'} predicted risk" for name, value in result["model_outputs"].items()]
    story.append(Paragraph("<br/>".join(model_lines), styles["BodySmall"]))
    story.append(Paragraph(f"Component model agreement: {result['model_consensus_count']}/{result['model_consensus_total']} component models indicate higher risk at the configured {result['model_threshold']:.0%} threshold. The hybrid is derived from these components and is not counted as a separate vote. {result['model_agreement_note']}", styles["BodySmall"]))
    section("5 · Explainable AI · hybrid prediction")
    story.append(Paragraph("The following features contributed to the final hybrid model prediction. Contributions are model explanations and are not proof of medical causation.", styles["BodySmall"]))
    factor_rows = [["Feature", "Patient value", "SHAP contribution", "Direction"]]
    for f in result["shap_values"][:8]:
        feature = f["feature"]
        raw = patient.get(feature)
        value_text = f"{raw:g}" if isinstance(raw, (int,float)) else str(raw)
        factor_rows.append([feature, value_text, f"{f['contribution']:+.5f}", f["direction"].title()])
    table(factor_rows, [1.75*inch, 1.45*inch, 1.55*inch, 1.3*inch])
    section("6 · Patient-specific contribution graph")
    story.append(Paragraph("The central node shows this assessment's model probability. Each connected feature node shows the entered patient value; the signed link label is that feature's SHAP contribution on the hybrid model probability scale (for example, +0.010 is about +1 percentage point of model output). Red contributions raise the model output and teal contributions lower it. These links describe this model's behavior, not statistical associations or medical causation. The explanation uses finite-evaluation permutation SHAP and is an approximation.", styles["BodySmall"]))
    story += [Spacer(1, 5), Image(graph_image, width=6.6*inch, height=4.35*inch),
              Paragraph(f"Graph method: {metadata.get('xai_method','SHAP')}. Model version: {metadata.get('model_version','not recorded')}. The graph uses the same ordered top {len(graph_data)} SHAP values shown on the assessment result page.", styles["BodySmall"])]
    section("7 · Risk stratification")
    story.append(Paragraph(f"This assessment falls in the <b>{category}</b> model-based category. Prototype cutoffs: low &lt; {metadata['risk_thresholds']['low_max_exclusive']:.0%}, moderate &lt; {metadata['risk_thresholds']['moderate_max_exclusive']:.0%}, high otherwise. These cutoffs are configurable and not clinically validated.", styles["BodySmall"]))
    section("8 · Intelligent decision support")
    for insight in result["decision_support"]: story.append(Paragraph("• " + insight, styles["BodySmall"]))
    section("9 · Limitations")
    for item in ["This is an academic/research prototype, not validated for clinical use.", "Predictions depend on the dataset quality and may not generalize to other populations.", "Feature contributions describe model behavior, not causation.", "External clinical validation is required before any clinical consideration.", "Risk categories are model-based and not necessarily clinically validated."]:
        story.append(Paragraph("• " + item, styles["BodySmall"]))
    section("10 · Disclaimer")
    story.append(Paragraph("This report is generated by an AI-based academic research prototype. It is not a medical diagnosis and should not replace assessment or advice from a qualified healthcare professional.", styles["Disclaimer"]))
    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D7E2E8"))
        canvas.line(.62*inch, .48*inch, 7.88*inch, .48*inch)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(.62*inch, .32*inch, "XAI-CVD · academic/research decision support")
        canvas.drawRightString(7.88*inch, .32*inch, f"Page {doc_.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
