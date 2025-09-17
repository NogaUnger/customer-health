# Health Score Methodology

The **Customer Health Score** is designed to provide a simple, explainable, and actionable measure of customer engagement, satisfaction, and retention risk.  
It produces a **0–100 score**, combining multiple behavioral and financial signals into a single metric.  

This document explains the methodology, rationale for factor selection, and tuning assumptions.

---

## Components (Sub-scores)

Each factor is normalized to a **0–100 scale** before weighting.

### 1. Login Frequency (25%)  
- **What it measures:** How often users log in during the last 30 days.  
- **Why it matters:** Frequent logins indicate adoption, habit-building, and ongoing value from the product.  
- **Normalization:** Customers are scored relative to expected seat usage (e.g., daily/weekly logins). Low login activity is one of the earliest churn signals.

---

### 2. Feature Adoption (25%)  
- **What it measures:** The percentage of distinct product features used in the last 30 days.  
- **Why it matters:** Healthy customers explore and use multiple features rather than relying on a single workflow.  
- **Normalization:** Customers using a broader set of features score higher. Stagnant or single-feature use suggests risk of disengagement.

---

### 3. Support Ticket Volume (20%)  
- **What it measures:** Number of tickets opened in the last 30 days, inverted (fewer tickets = better).  
- **Why it matters:** High ticket volume can mean poor product experience or unresolved issues, driving dissatisfaction.  
- **Normalization:** Customers with zero or low tickets receive the highest scores, while frequent ticket raisers are penalized.

---

### 4. Invoice Timeliness (15%)  
- **What it measures:** Ratio of invoices paid on time vs. late within the last 90 days.  
- **Why it matters:** Timely payments are a proxy for customer satisfaction and financial reliability. Late payments may indicate disengagement or business instability.  
- **Normalization:** 100 = all invoices paid on time; 0 = all invoices late.

---

### 5. API Usage Trend (15%)  
- **What it measures:** API calls in the last 7 days compared to the previous 7 days.  
- **Why it matters:** Growth in API usage often signals deeper integration of the product into customer workflows. Decline suggests reduced reliance on the platform.  
- **Normalization:**  
  - Trend up = higher than 50.  
  - Flat = ~50.  
  - Trend down = lower than 50.

---

## Weights

- `login_frequency`: **0.25**  
- `feature_adoption`: **0.25**  
- `support_ticket_volume`: **0.20**  
- `invoice_timeliness`: **0.15**  
- `api_usage_trend`: **0.15**

These weights prioritize **engagement (50%)** while balancing **support/financial reliability (35%)** and **technical integration (15%)**.

---

## Interpretation

- **80–100 → Healthy** ✅ Strong adoption and low churn risk.  
- **40–79 → Watchlist** ⚠️ Moderate risk; customer success should investigate.  
- **0–39 → At risk** 🚨 High churn likelihood; urgent intervention required.  

---

## Assumptions & Tuning Notes

- Factors are chosen to balance **behavioral signals** (logins, feature use), **product experience** (tickets), and **business signals** (invoices, API use).  
- Weights are designed for **explainability** over pure predictive accuracy, making the score understandable to non-technical stakeholders.  
- Thresholds were selected for **stability on small datasets** while still producing meaningful distributions.  
- In the future:  
  - **Segment-specific weights** (e.g., SMBs may care more about feature adoption; enterprises may prioritize invoices).  
  - **Advanced models** (regression or ML) could refine the weighting scheme with real churn data.  

---

## Example Calculation

If a customer has:
- Login frequency: 80  
- Feature adoption: 100  
- Support tickets: 70  
- Invoice timeliness: 60  
- API trend: 90  

Final score =  
`0.25*80 + 0.25*100 + 0.20*70 + 0.15*60 + 0.15*90 = 82.5` → **Healthy** ✅
