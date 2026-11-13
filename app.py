import os
import re
import sqlite3
import uuid
from datetime import datetime

from flask import (
    Flask, request, jsonify, render_template_string
)
from werkzeug.utils import secure_filename

# Optional document processing libraries
try:
    import pymupdf
except ImportError:
    pymupdf = None

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None


# ==========================================
# 1. APPLICATION CONFIGURATION
# ==========================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DATABASE = os.path.join(BASE_DIR, "insurance.db")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


# ==========================================
# 2. DATABASE CONFIGURATION
# ==========================================

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def initialize_database():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_reference TEXT UNIQUE,
                customer_name TEXT,
                policy_number TEXT,
                policy_type TEXT,
                incident_type TEXT,
                incident_date TEXT,
                incident_description TEXT,
                claim_amount REAL,
                document_name TEXT,
                extracted_text TEXT,
                review_result TEXT,
                status TEXT,
                created_at TEXT
            )
        """)


initialize_database()


# ==========================================
# 3. DOCUMENT UPLOAD AND OCR
# ==========================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def extract_document_text(file_path):
    extension = file_path.rsplit(".", 1)[1].lower()

    try:
        # Extract text from PDF
        if extension == "pdf":
            if pymupdf is None:
                return "PDF extraction unavailable. Install PyMuPDF."

            document = pymupdf.open(file_path)
            text = ""

            for page in document:
                text += page.get_text() + "\n"

            document.close()

            if not text.strip():
                return (
                    "No selectable text found in this PDF. "
                    "Scanned PDF OCR is not configured."
                )

            return text[:10000]

        # Extract text from images using Tesseract OCR
        if extension in ["png", "jpg", "jpeg"]:
            if pytesseract is None or Image is None:
                return "Image OCR unavailable. Install Tesseract and its Python packages."

            tesseract_path = (
                r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            )

            if os.path.exists(tesseract_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_path

            text = pytesseract.image_to_string(
                Image.open(file_path)
            )

            return text[:10000] if text.strip() else "No readable text found."

    except Exception as error:
        return "Document extraction error: " + str(error)

    return "Unsupported document format."


# ==========================================
# 4. PRELIMINARY POLICY REVIEW
# ==========================================

def review_claim(policy_type, incident_type, description, amount, extracted_text):

    issues = []

    if not description.strip():
        issues.append("Incident description is missing.")

    if amount <= 0:
        issues.append("Invalid claim amount.")

    policy = policy_type.lower()
    incident = incident_type.lower()

    # Demonstration policy-category matching
    if policy == "health insurance" and incident != "medical":
        issues.append(
            "The incident category does not match health insurance."
        )

    elif policy == "vehicle insurance" and incident != "vehicle accident":
        issues.append(
            "The incident category does not match vehicle insurance."
        )

    elif policy == "life insurance" and incident != "life":
        issues.append(
            "The incident category does not match life insurance."
        )

    elif policy == "travel insurance" and incident != "travel":
        issues.append(
            "The incident category does not match travel insurance."
        )

    # Basic document check
    if not extracted_text.strip():
        issues.append("Supporting document text is not available.")

    # Amount extraction for preliminary comparison
    amounts = re.findall(
        r"(?:total|amount|grand total|bill amount)[^\d]{0,25}"
        r"([\d,]+(?:\.\d{1,2})?)",
        extracted_text,
        re.IGNORECASE
    )

    if amounts:
        try:
            document_amount = float(amounts[0].replace(",", ""))

            if abs(document_amount - amount) > 1:
                issues.append(
                    "Claim amount differs from the amount found in the document."
                )
        except ValueError:
            pass

    if issues:
        return (
            "Needs Manual Review",
            "Preliminary checks found the following issues:\n- "
            + "\n- ".join(issues)
        )

    return (
        "Preliminary Checks Passed",
        "The submitted information passed the basic demonstration checks. "
        "Actual policy coverage, exclusions, validity and claim eligibility "
        "must still be verified by an authorized insurer."
    )


# ==========================================
# 5. MAIN WEBSITE - HTML, CSS AND JAVASCRIPT
# ==========================================

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>AI Insurance Claim Assistant</title>

<style>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: Arial, sans-serif;
    background: #f3f6fb;
    color: #17243b;
}

header {
    background: #142c50;
    color: white;
    padding: 20px 6%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 15px;
}

header h2 {
    font-size: 23px;
}

nav {
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
}

nav a {
    color: white;
    text-decoration: none;
    font-size: 14px;
}

.hero {
    background: linear-gradient(120deg, #173c70, #2874c8);
    color: white;
    padding: 55px 7%;
}

.hero h1 {
    font-size: 34px;
    margin-bottom: 15px;
}

.hero p {
    line-height: 1.7;
    max-width: 700px;
}

.container {
    max-width: 1150px;
    margin: 30px auto;
    padding: 0 20px;
}

.section {
    background: white;
    padding: 25px;
    margin-bottom: 25px;
    border-radius: 12px;
    box-shadow: 0 3px 12px #0000000c;
}

.section h2 {
    margin-bottom: 18px;
    color: #183d70;
}

.cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 18px;
    margin-bottom: 25px;
}

.card {
    background: white;
    padding: 23px;
    border-radius: 12px;
    box-shadow: 0 3px 12px #0000000c;
}

.card h3 {
    color: #2869bb;
    margin-bottom: 10px;
}

label {
    display: block;
    font-weight: bold;
    margin: 15px 0 7px;
}

input, select, textarea {
    width: 100%;
    padding: 12px;
    border: 1px solid #cbd5e1;
    border-radius: 7px;
    font-size: 15px;
    font-family: Arial;
}

textarea {
    min-height: 100px;
    resize: vertical;
}

button {
    background: #2468c5;
    color: white;
    padding: 12px 20px;
    border: none;
    border-radius: 7px;
    cursor: pointer;
    font-size: 15px;
    margin-top: 17px;
}

button:hover {
    background: #174d96;
}

.result {
    margin-top: 18px;
    padding: 15px;
    border-radius: 8px;
    background: #edf4ff;
    white-space: pre-wrap;
    line-height: 1.6;
    overflow-wrap: anywhere;
}

.hidden {
    display: none;
}

.table-wrap {
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
    min-width: 650px;
}

th, td {
    padding: 13px;
    text-align: left;
    border-bottom: 1px solid #e4e9f0;
}

th {
    background: #edf3fb;
}

.status {
    font-weight: bold;
    color: #a45c0b;
}

.chat-answer {
    background: #edf4ff;
    padding: 15px;
    border-radius: 8px;
    margin-top: 15px;
    line-height: 1.6;
}

footer {
    text-align: center;
    background: #142c50;
    color: white;
    padding: 23px;
    margin-top: 40px;
}

.small {
    color: #64748b;
    font-size: 13px;
    line-height: 1.5;
    margin-top: 10px;
}

@media(max-width: 600px) {
    header {
        align-items: flex-start;
    }

    .hero h1 {
        font-size: 27px;
    }

    nav {
        gap: 12px;
    }
}
</style>
</head>

<body>

<header>
    <h2>AI Insurance Claim Assistant</h2>

    <nav>
        <a href="#home">Home</a>
        <a href="#submit">Submit Claim</a>
        <a href="#tracking">Track Claim</a>
        <a href="#assistant">AI Assistant</a>
    </nav>
</header>


<!-- HOME SECTION -->

<section class="hero" id="home">
    <h1>Smart Insurance Claim Management</h1>

    <p>
        A digital self-service portal that helps claimants describe
        incidents, submit insurance claim details, upload supporting
        documents, extract information using OCR, receive preliminary
        policy-based review and track claim progress.
    </p>
</section>


<div class="container">

    <!-- DASHBOARD -->

    <div class="cards">
        <div class="card">
            <h3>Total Claims</h3>
            <h2 id="totalClaims">0</h2>
        </div>

        <div class="card">
            <h3>Under Review</h3>
            <h2 id="reviewClaims">0</h2>
        </div>

        <div class="card">
            <h3>Submitted</h3>
            <h2 id="submittedClaims">0</h2>
        </div>
    </div>


    <!-- CLAIM SUBMISSION -->

    <section class="section" id="submit">

        <h2>Submit a New Insurance Claim</h2>

        <form id="claimForm">

            <label>Customer Name</label>
            <input type="text" name="customer_name" required
                   placeholder="Enter your full name">

            <label>Policy Number</label>
            <input type="text" name="policy_number" required
                   placeholder="Example: HLT-2026-10025">

            <label>Insurance Type</label>
            <select name="policy_type" required>
                <option value="">Select insurance type</option>
                <option>Health Insurance</option>
                <option>Vehicle Insurance</option>
                <option>Life Insurance</option>
                <option>Travel Insurance</option>
            </select>

            <label>Incident Category</label>
            <select name="incident_type" required>
                <option value="">Select incident category</option>
                <option>Medical</option>
                <option>Vehicle Accident</option>
                <option>Life</option>
                <option>Travel</option>
            </select>

            <label>Incident Date</label>
            <input type="date" name="incident_date" required>

            <label>Describe the Incident</label>
            <textarea name="incident_description" required
                placeholder="Explain what happened, when it happened and the details of your claim..."></textarea>

            <label>Claim Amount (₹)</label>
            <input type="number" name="claim_amount"
                   min="1" step="0.01" required
                   placeholder="Enter claim amount">

            <label>Upload Supporting Document</label>
            <input type="file" name="document"
                   accept=".pdf,.png,.jpg,.jpeg">

            <p class="small">
                Accepted formats: PDF, PNG, JPG and JPEG.
                Maximum file size: 10 MB.
            </p>

            <button type="submit">Submit Insurance Claim</button>

        </form>

        <div id="claimResult" class="result hidden"></div>

    </section>


    <!-- TRACKING -->

    <section class="section" id="tracking">

        <h2>Track Your Insurance Claim</h2>

        <p class="small">
            Enter the claim reference number and policy number
            received after submitting your claim.
        </p>

        <label>Claim Reference Number</label>
        <input type="text" id="trackReference"
               placeholder="Example: CLM-2026-123456">

        <label>Policy Number</label>
        <input type="text" id="trackPolicy"
               placeholder="Enter your policy number">

        <button onclick="trackClaim()">Track Claim</button>

        <div id="trackingResult" class="result hidden"></div>

    </section>


    <!-- CLAIM RECORDS -->

    <section class="section">

        <h2>Recent Claim Records</h2>

        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Reference</th>
                        <th>Customer</th>
                        <th>Insurance</th>
                        <th>Amount</th>
                        <th>Status</th>
                    </tr>
                </thead>

                <tbody id="claimTable">
                    <tr>
                        <td colspan="5">No claims loaded.</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <button onclick="loadClaims()">Refresh Records</button>

        <p class="small">
            This demonstration shows claim records stored in its local database.
        </p>

    </section>


    <!-- OCR -->

    <section class="section">

        <h2>Document Extraction (OCR)</h2>

        <p>
            The system extracts readable text from uploaded supporting
            documents to assist the preliminary review process.
        </p>

        <p class="small">
            Document text is extracted during claim submission.
            The extracted text is displayed in the submission result.
        </p>

    </section>


    <!-- AI ASSISTANT -->

    <section class="section" id="assistant">

        <h2>AI Insurance Assistant</h2>

        <p>
            Ask questions about claim submission, policy details,
            document requirements and claim tracking.
        </p>

        <label>Your Question</label>

        <input type="text" id="chatQuestion"
               placeholder="Example: What documents are required for a claim?">

        <button onclick="askAssistant()">Ask Assistant</button>

        <div id="chatResult" class="chat-answer hidden"></div>

        <p class="small">
            This version uses a rule-based assistant for demonstration.
            It is not connected to a live language model.
        </p>

    </section>


    <!-- PROJECT INFORMATION -->

    <section class="section">

        <h2>How the System Works</h2>

        <ol style="padding-left:22px; line-height:2;">
            <li>Claimant enters personal and insurance details.</li>
            <li>Claimant describes the incident.</li>
            <li>Supporting documents are uploaded.</li>
            <li>OCR extracts available document text.</li>
            <li>Preliminary checks examine submitted information.</li>
            <li>Claim details are stored in the database.</li>
            <li>Claimant can track the claim using its reference number.</li>
        </ol>

        <p class="small">
            Policy matching in this academic prototype is illustrative.
            It does not verify real insurer policy records, exclusions,
            policy validity or actual claim eligibility.
        </p>

    </section>

</div>


<footer>
    <p>AI Insurance Claim Assistant</p>
    <p class="small" style="color:#d5e2f4;">
        Digital Self-Service Insurance Claim Portal | Academic Project
    </p>
</footer>


<script>

// ======================================
// SUBMIT CLAIM
// ======================================

document.getElementById("claimForm").addEventListener(
    "submit", async function(event) {

    event.preventDefault();

    const formData = new FormData(this);

    const resultBox = document.getElementById("claimResult");

    resultBox.classList.remove("hidden");
    resultBox.innerText = "Submitting claim and processing document...";

    try {
        const response = await fetch("/api/claims", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Claim submission failed.");
        }

        resultBox.innerText =
            "Claim submitted successfully!\n\n" +
            "Reference Number: " + data.reference + "\n" +
            "Status: " + data.status + "\n\n" +
            "Preliminary Review:\n" + data.review + "\n\n" +
            "Extracted Document Text:\n" +
            data.extracted_text;

        this.reset();

        loadClaims();

    } catch(error) {
        resultBox.innerText = "Error: " + error.message;
    }
});


// ======================================
// TRACK CLAIM
// ======================================

async function trackClaim() {

    const reference =
        document.getElementById("trackReference").value.trim();

    const policy =
        document.getElementById("trackPolicy").value.trim();

    const resultBox =
        document.getElementById("trackingResult");

    resultBox.classList.remove("hidden");

    if (!reference || !policy) {
        resultBox.innerText =
            "Please enter both claim reference and policy number.";
        return;
    }

    try {
        const response = await fetch(
            "/api/claims/" + encodeURIComponent(reference) +
            "?policy=" + encodeURIComponent(policy)
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Claim not found.");
        }

        resultBox.innerText =
            "Claim Reference: " + data.reference + "\n" +
            "Customer: " + data.customer + "\n" +
            "Insurance Type: " + data.policy_type + "\n" +
            "Incident: " + data.incident_type + "\n" +
            "Claim Amount: ₹" + data.amount + "\n" +
            "Status: " + data.status + "\n" +
            "Submitted On: " + data.created_at;

    } catch(error) {
        resultBox.innerText = error.message;
    }
}


// ======================================
// LOAD CLAIM RECORDS
// ======================================

async function loadClaims() {

    try {
        const response = await fetch("/api/claims");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Unable to load claims.");
        }

        const table = document.getElementById("claimTable");

        table.innerHTML = "";

        data.claims.forEach(claim => {

            const row = document.createElement("tr");

            [
                claim.reference,
                claim.customer,
                claim.policy_type,
                "₹" + claim.amount,
                claim.status
            ].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value;
                row.appendChild(cell);
            });

            table.appendChild(row);
        });

        document.getElementById("totalClaims").innerText =
            data.claims.length;

        document.getElementById("reviewClaims").innerText =
            data.claims.filter(c =>
                c.status === "Needs Manual Review"
            ).length;

        document.getElementById("submittedClaims").innerText =
            data.claims.filter(c =>
                c.status === "Preliminary Checks Passed"
            ).length;

        if (data.claims.length === 0) {
            table.innerHTML =
                '<tr><td colspan="5">No claims submitted yet.</td></tr>';
        }

    } catch(error) {
        console.error(error);
    }
}


// ======================================
// AI ASSISTANT
// ======================================

async function askAssistant() {

    const question =
        document.getElementById("chatQuestion").value.trim();

    const result =
        document.getElementById("chatResult");

    result.classList.remove("hidden");

    if (!question) {
        result.innerText = "Please enter a question.";
        return;
    }

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({question: question})
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Assistant unavailable.");
        }

        result.innerText = data.answer;

    } catch(error) {
        result.innerText = error.message;
    }
}


// Load dashboard records when page opens
loadClaims();

</script>

</body>
</html>
"""


# ==========================================
# 6. HOME PAGE
# ==========================================

@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML)


# ==========================================
# 7. CLAIM SUBMISSION API
# ==========================================

@app.route("/api/claims", methods=["POST"])
def submit_claim():

    customer = request.form.get("customer_name", "").strip()
    policy_number = request.form.get("policy_number", "").strip()
    policy_type = request.form.get("policy_type", "").strip()
    incident_type = request.form.get("incident_type", "").strip()
    incident_date = request.form.get("incident_date", "").strip()
    description = request.form.get("incident_description", "").strip()
    amount_text = request.form.get("claim_amount", "").strip()

    if not all([
        customer, policy_number, policy_type,
        incident_type, incident_date, description, amount_text
    ]):
        return jsonify({"error": "Please complete all required fields."}), 400

    try:
        amount = float(amount_text)

        if amount <= 0:
            raise ValueError()

    except ValueError:
        return jsonify({"error": "Enter a valid claim amount."}), 400

    try:
        datetime.strptime(incident_date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Enter a valid incident date."}), 400

    document = request.files.get("document")

    filename = ""
    extracted_text = "No supporting document uploaded."

    if document and document.filename:

        if not allowed_file(document.filename):
            return jsonify({
                "error": "Only PDF, PNG, JPG and JPEG files are allowed."
            }), 400

        safe_name = secure_filename(document.filename)

        filename = (
            uuid.uuid4().hex + "_" + safe_name
        )

        file_path = os.path.join(UPLOAD_FOLDER, filename)

        document.save(file_path)

        extracted_text = extract_document_text(file_path)

    status, review = review_claim(
        policy_type,
        incident_type,
        description,
        amount,
        extracted_text
    )

    reference = "CLM-" + datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6].upper()

    with get_db() as db:
        db.execute("""
            INSERT INTO claims (
                claim_reference,
                customer_name,
                policy_number,
                policy_type,
                incident_type,
                incident_date,
                incident_description,
                claim_amount,
                document_name,
                extracted_text,
                review_result,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            reference,
            customer,
            policy_number,
            policy_type,
            incident_type,
            incident_date,
            description,
            amount,
            filename,
            extracted_text,
            review,
            status,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    return jsonify({
        "message": "Claim submitted successfully.",
        "reference": reference,
        "status": status,
        "review": review,
        "extracted_text": extracted_text[:3000]
    })


# ==========================================
# 8. CLAIM TRACKING API
# ==========================================

@app.route("/api/claims/<reference>", methods=["GET"])
def track_claim(reference):

    policy = request.args.get("policy", "").strip()

    with get_db() as db:
        claim = db.execute("""
            SELECT * FROM claims
            WHERE claim_reference = ?
            AND policy_number = ?
        """, (reference, policy)).fetchone()

    if claim is None:
        return jsonify({
            "error": "No matching claim found. Check your reference and policy number."
        }), 404

    return jsonify({
        "reference": claim["claim_reference"],
        "customer": claim["customer_name"],
        "policy_type": claim["policy_type"],
        "incident_type": claim["incident_type"],
        "amount": claim["claim_amount"],
        "status": claim["status"],
        "created_at": claim["created_at"]
    })


# ==========================================
# 9. VIEW ALL CLAIMS API
# ==========================================

@app.route("/api/claims", methods=["GET"])
def get_claims():

    with get_db() as db:
        records = db.execute("""
            SELECT claim_reference, customer_name,
                   policy_type, claim_amount, status
            FROM claims
            ORDER BY id DESC
        """).fetchall()

    claims = []

    for row in records:
        claims.append({
            "reference": row["claim_reference"],
            "customer": row["customer_name"],
            "policy_type": row["policy_type"],
            "amount": row["claim_amount"],
            "status": row["status"]
        })

    return jsonify({"claims": claims})


# ==========================================
# 10. AI CHATBOT API
# ==========================================

@app.route("/api/chat", methods=["POST"])
def chatbot():

    data = request.get_json(silent=True) or {}

    question = data.get("question", "").lower().strip()

    if not question:
        return jsonify({"error": "Enter a question."}), 400

    if any(word in question for word in [
        "submit", "claim", "apply"
    ]):
        answer = (
            "To submit an insurance claim, enter your customer details, "
            "policy information, incident description and claim amount. "
            "Upload the supporting document and select Submit Insurance Claim. "
            "The system will generate a claim reference number."
        )

    elif any(word in question for word in [
        "document", "upload", "file", "paper"
    ]):
        answer = (
            "You can upload supporting documents in PDF, PNG, JPG or JPEG "
            "format. Examples include hospital bills, discharge summaries, "
            "vehicle repair bills, photographs and incident reports, "
            "depending on the type of claim."
        )

    elif any(word in question for word in [
        "status", "track", "progress"
    ]):
        answer = (
            "To track your claim, open the Track Your Insurance Claim "
            "section. Enter your claim reference number and policy number "
            "to view its current status."
        )

    elif any(word in question for word in [
        "ocr", "extract", "text"
    ]):
        answer = (
            "OCR stands for Optical Character Recognition. It helps extract "
            "readable text from uploaded documents. The extracted text can "
            "support preliminary claim review."
        )

    elif any(word in question for word in [
        "policy", "coverage", "eligible"
    ]):
        answer = (
            "Policy coverage depends on the actual insurance contract, "
            "validity period, exclusions and conditions. This prototype "
            "performs only basic demonstration checks and cannot verify "
            "real insurer policy records."
        )

    elif any(word in question for word in [
        "amount", "bill", "money"
    ]):
        answer = (
            "Enter the claim amount shown in your supporting documents. "
            "The prototype can compare an amount found in extracted text "
            "with the amount you entered."
        )

    else:
        answer = (
            "Hello! I can help you with claim submission, policy information, "
            "document uploads, OCR and claim tracking. Please ask a question "
            "about one of these topics."
        )

    return jsonify({"answer": answer})


# ==========================================
# 11. ERROR HANDLING
# ==========================================

@app.errorhandler(404)
def page_not_found(error):
    return """
    <h1>Page Not Found</h1>
    <p>Please open the application homepage:</p>
    <a href="/">AI Insurance Claim Assistant</a>
    """, 404


@app.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "error": "File too large. Maximum allowed size is 10 MB."
    }), 413


# ==========================================
# 12. START APPLICATION
# ==========================================

if __name__ == "__main__":

    print("=" * 55)
    print("AI INSURANCE CLAIM ASSISTANT")
    print("=" * 55)
    print("Application: http://127.0.0.1:5000/")
    print("Database: insurance.db")
    print("Uploads folder: uploads/")
    print("=" * 55)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )