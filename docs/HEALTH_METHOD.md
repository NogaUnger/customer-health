# Health Score Methodology

The **Customer Health Score** is a unified metric (0–100) that combines behavioral, product usage, support, and financial signals to indicate overall customer well-being.  
It helps Customer Success and Product teams quickly identify **healthy customers**, **those needing attention**, and **those at churn risk**.  

---

## Components (Sub-scores)

Each factor is normalized to a **0–100 scale** before weighting.

### 1. Login Frequency (25%)  
- **What it measures:** How often users log in during the last 30 days.  
- **Why it matters:** Consistent logins indicate adoption and product stickiness. Low login activity is often the earliest warning sign of disengagement.  
- **Normalization:** Higher scores for customers with frequent logins relative to seat count.

---

### 2. Feature Adoption (20%)  
- **What it measures:** Percentage of distinct product features used in the last 30 days.  
- **Why it matters:** Customers using multiple features are more deeply engaged and less likely to churn. Narrow usage suggests shallow adoption and risk of replacement.  
- **Normalization:** Broader feature usage = higher score.

---

### 3. Support Ticket Volume (25%)  
- **What it measures:** Number of tickets opened in the last 30 days (inverted — fewer is better).  
- **Why it matters:** High ticket volume can reflect product friction or dissatisfaction. Fewer tickets usually mean smoother experience.  
- **Normalization:** Zero or low tickets = 100; frequent tickets reduce the score.

---

### 4. Invoice Timeliness (20%)  
- **What it measures:** Ratio of invoices paid on time vs. late within the last 90 days.  
- **Why it matters:** Timely payments correlate with customer satisfaction and financial stability. Late payments may indicate churn risk or internal disengagement.  
- **Normalization:** 100 = all invoices on time; 0 = all late.

---

### 5. API Usage Trend (10%)  
- **What it measures:** Change in API calls over the last 7 days compared to the previous 7 days.  
- **Why it matters:** Growth in API usage signals deeper integration into customer workflows. Decline suggests reduced reliance on the platform.  
- **Normalization:**  
  - Upward trend → high score.  
  - Flat → ~50.  
  - Decline → low score.  

---

## Weights

- `login_frequency`: **25%**  
- `feature_adoption`: **20%**  
- `support_ticket_volume`: **25%**  
- `invoice_timeliness`: **20%**  
- `api_usage_trend`: **10%**

This balance reflects:  
- **Engagement** (login + feature = 45%)  
- **Experience** (support tickets = 25%)  
- **Financial reliability** (invoices = 20%)  
- **Technical integration** (API = 10%)

---

## Interpretation

- **80–100 → Healthy** ✅ Strong adoption and low churn risk.  
- **40–79 → Watchlist** ⚠️ Some risks detected; proactive check-in advised.  
- **0–39 → At risk** 🚨 High churn likelihood; immediate intervention required.  

---

## Assumptions & Tuning Notes

- Chosen factors balance **behavior**, **experience**, and **financial health**, providing a rounded view.  
- Weights emphasize **user engagement and product adoption** (45%) because these are leading churn predictors.  
- Thresholds (Healthy/Watchlist/At risk) are set for **clarity and explainability**, not predictive optimization.  
- In the future:  
  - Adjust weights per **segment** (e.g., enterprises may weigh invoices more heavily).  
  - Train a **predictive model** on real churn data to optimize weights.  

---

## Example Calculation

If a customer has:
- Login frequency: 80  
- Feature adoption: 60  
- Support tickets: 50  
- Invoice timeliness: 100  
- API trend: 40  

Final score =  
`0.25*80 + 0.20*60 + 0.25*50 + 0.20*100 + 0.10*40 = 71` → **Watchlist** ⚠️
