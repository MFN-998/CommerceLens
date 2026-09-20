Below is a **GPT Work–ready version** of the CommerceLens master plan. It is written so you can paste it directly into GPT Work as the project brief and source of truth.

# CommerceLens — Master Project Plan

## 1. Project Status

This document is the **canonical source of truth** for the CommerceLens project.

GPT Work should use this document to guide all implementation work.

Do not redesign the project from scratch unless explicitly instructed.

Future implementation work should be divided by major project phase, and each phase should follow this plan.

---

# 2. Working Directory

Use the following local working directory for all project work:

`D:\My Projects\CommerceLens`

All commands, repository setup, file paths, environments, scripts, and project instructions should assume this directory unless explicitly changed later.

---

# 3. Project Identity

**Project Name:** CommerceLens

**Working Tagline:**  
From commerce data to business decisions.

**Project Type:**  
Full-stack Data Analytics + Data Science + Data Engineering portfolio application.

**Domain:**  
E-commerce / retail analytics.

**Primary Objective:**  
Build a real, publicly accessible, interactive data product that demonstrates the complete real-world data lifecycle:

Business problem → data acquisition → ingestion → cleaning → modeling → SQL → analytics → statistics → machine learning → APIs → frontend → deployment → business recommendations.

CommerceLens must not become merely a dashboard or notebook-based ML project.

The goal is to create a realistic **decision-intelligence platform for e-commerce businesses**.

---

# 4. Core Product Vision

CommerceLens should transform raw e-commerce data into:

- Business KPIs
- Sales analytics
- Product analytics
- Customer intelligence
- Customer segmentation
- Cohort analysis
- Retention analysis
- Seller performance
- Logistics analytics
- Customer satisfaction analysis
- Late-delivery risk prediction
- Demand forecasting
- Decision recommendations

The finished project should look and behave like a real analytics SaaS product.

---

# 5. Target Users

The platform should be understandable and useful to:

- Business managers
- Analysts
- Operations teams
- Data scientists
- Recruiters
- Hiring managers
- Portfolio reviewers

The public website should allow anyone to explore the system without requiring login.

---

# 6. Main Dataset

Use the **Olist Brazilian E-Commerce Public Dataset** as the initial dataset.

The dataset contains approximately 100,000 anonymized e-commerce orders and includes information related to:

- Orders
- Customers
- Products
- Sellers
- Order items
- Payments
- Reviews
- Delivery/logistics
- Geography

CommerceLens must clearly state that this is historical anonymized data.

Do not pretend the historical dataset represents a live 2026 business.

The **application** is live; the underlying dataset is historical.

---

# 7. Main Learning Objectives

CommerceLens should teach and demonstrate:

## Business and Analytics

- Business problem framing
- KPI definition
- Business metrics
- Exploratory analysis
- Root-cause investigation
- Business recommendations
- Data storytelling

## Data Engineering

- Raw/staging/core/mart architecture
- ETL/ELT concepts
- PostgreSQL
- Data validation
- Data modeling
- Dimensional modeling
- Fact/dimension tables
- Data quality
- dbt
- Reproducible pipelines

## SQL

- Joins
- Aggregations
- CTEs
- Window functions
- Cohorts
- Retention
- Segmentation
- Analytical queries

## Data Science

- Feature engineering
- Classification
- Clustering
- Time-series forecasting
- Baselines
- Evaluation
- Leakage prevention
- Explainability
- Threshold selection

## Statistics

- Hypothesis testing
- Confidence intervals
- Effect sizes
- Correlation
- Distribution comparisons
- Statistical vs business significance
- Association vs causality

## Software Engineering

- Git
- GitHub
- Modular code
- Environment management
- Testing
- API design
- Configuration management
- CI/CD
- Logging
- Security
- Documentation

## Product Development

- FastAPI
- Next.js
- React
- TypeScript
- Supabase/PostgreSQL
- Interactive dashboards
- Public deployment

---

# 8. Data Architecture

Use a layered architecture.

## Layer 1 — Raw

Immutable copies of the original source data.

Purpose:

- Preserve original data
- Enable reproducibility
- Avoid accidental source modifications

## Layer 2 — Staging

Clean and standardized data.

Typical operations:

- Rename fields
- Standardize datatypes
- Handle timestamps
- Validate identifiers
- Normalize text
- Document missing values

## Layer 3 — Core

Business-ready dimensional models.

Use fact and dimension tables.

## Layer 4 — Analytics Marts

Tables optimized for specific analytical use cases.

Examples:

- Executive KPIs
- Customer analytics
- Sales analytics
- Product performance
- Seller performance
- Logistics
- Reviews
- Geography
- Cohorts

## Layer 5 — Feature Tables

ML-ready datasets.

Examples:

- Delivery risk features
- Customer segmentation features
- Forecasting datasets

## Layer 6 — API

FastAPI exposes analytics and model predictions.

## Layer 7 — Web Application

Next.js frontend consumes the API and displays analytics.

Architecture:

Source Data  
→ Raw  
→ Staging  
→ Core Models  
→ Analytics Marts / ML Features  
→ FastAPI  
→ CommerceLens Web App

---

# 9. Core Data Model

## Dimension Tables

Potential dimensions:

- `dim_customer`
- `dim_product`
- `dim_seller`
- `dim_date`
- `dim_location`

## Fact Tables

Potential facts:

- `fact_orders`
- `fact_order_items`
- `fact_payments`
- `fact_reviews`
- `fact_delivery`

The exact design should be finalized after profiling the actual source data.

---

# 10. Grain Management

Data grain must be explicitly defined for every table.

Example:

- Orders: one row per order
- Order items: one row per order item
- Payments: one row per payment transaction or defined aggregation
- Reviews: review-level grain

Avoid incorrect joins that multiply records.

Example risk:

Joining orders directly to multiple order items and multiple payment records can artificially inflate GMV.

CommerceLens must detect and prevent these issues.

---

# 11. Analytics Marts

Expected marts may include:

- `mart_executive_kpis`
- `mart_sales_daily`
- `mart_product_performance`
- `mart_customer_360`
- `mart_rfm`
- `mart_cohort_retention`
- `mart_seller_performance`
- `mart_logistics`
- `mart_geography`
- `mart_review_analysis`

Names may be adjusted during implementation if justified.

---

# 12. KPI Framework

All KPIs must have documented definitions.

Examples:

## Commerce Metrics

- GMV
- Orders
- Units sold
- Average order value
- Active customers

## Customer Metrics

- New customers
- Repeat customers
- Repeat purchase rate
- Recency
- Frequency
- Monetary value

## Delivery Metrics

- Average delivery duration
- Late-delivery rate
- On-time rate
- Estimated vs actual delivery difference

## Satisfaction Metrics

- Mean review score
- Low-rating rate
- High-rating rate

## Seller Metrics

- Seller GMV
- Seller orders
- Seller late-delivery rate
- Seller rating

## Geographic Metrics

- Orders by state/region
- GMV by geography
- Customer concentration
- Seller concentration

Do not call GMV "profit."

Do not call GMV accounting revenue unless clearly justified.

---

# 13. Main Application Modules

## Module 1 — Executive Overview

Purpose:

Give management a fast view of business performance.

Expected elements:

- GMV
- Orders
- Customers
- AOV
- Satisfaction
- Sales trends
- Top categories
- Delivery performance
- Customer trends
- Geographic performance
- Business alerts

---

# 14. Module 2 — Sales & Product Intelligence

Questions to answer:

- What is selling?
- Where is demand coming from?
- Which categories dominate order value?
- Which products/categories have operational issues?
- How does performance change over time?
- Are there high-volume categories with poor delivery performance?

Potential analyses:

- Sales trends
- Product/category ranking
- Price distribution
- Freight burden
- Category share
- Seasonal patterns
- Category satisfaction
- Category delivery performance

---

# 15. Module 3 — Customer Intelligence

## Customer 360

Customer-level metrics such as:

- Orders
- Total spend
- Average order value
- Recency
- Frequency
- First order
- Last order
- Preferred categories
- Satisfaction

## RFM Analysis

Use:

- Recency
- Frequency
- Monetary value

Create interpretable business segments.

## Cohort Analysis

Group customers by first purchase period.

Measure subsequent activity and retention.

Display interactive cohort matrices.

---

# 16. ML Problem 1 — Customer Segmentation

Start with behavioral customer features.

Potential pipeline:

Raw customer features  
→ cleaning  
→ transformations  
→ scaling  
→ clustering  
→ evaluation  
→ interpretation

K-Means may be used as an initial candidate.

Do not arbitrarily choose the number of clusters.

Evaluate clusters using:

- Silhouette score
- Cluster sizes
- Stability
- Feature distributions
- Business interpretability

Cluster labels should be assigned only after examining actual cluster behavior.

---

# 17. Module 4 — Logistics Intelligence

Analyze the order lifecycle:

Purchase  
→ approval  
→ seller/carrier handling  
→ estimated delivery  
→ actual delivery  
→ customer review

Questions include:

- Where are delays occurring?
- Which sellers have poor delivery performance?
- Which regions experience longer delivery times?
- Which categories experience delays?
- How strongly are delays associated with low reviews?
- Does freight cost relate to delivery outcomes?

---

# 18. ML Problem 2 — Late Delivery Risk

This should be the flagship supervised ML problem.

## Business Question

Can CommerceLens identify orders with elevated risk of late delivery using information available near order time?

## Target

Binary:

- `1` = late
- `0` = on time

## Candidate Features

Examples:

- Order timing
- Product/category
- Customer geography
- Seller geography
- Price
- Freight value
- Product characteristics
- Historical seller metrics

Exact features must be justified after EDA.

## Leakage Prevention

Do not use information that would not exist at prediction time.

Examples of forbidden leakage features:

- Actual delivery date
- Actual delivery duration
- Final review score
- Any post-delivery field

## Candidate Models

Start with baseline models.

Suggested progression:

1. Simple baseline
2. Logistic regression
3. Tree-based models
4. Additional models only if justified

## Evaluation

Include:

- Precision
- Recall
- F1
- ROC-AUC
- PR-AUC
- Confusion matrix
- Probability calibration
- Business threshold analysis

Accuracy alone is insufficient.

---

# 19. ML Problem 3 — Demand Forecasting

Business question:

What demand should the business expect in future periods?

Possible forecasting targets:

- Weekly total orders
- Weekly GMV
- Weekly category demand

Determine the appropriate grain after analyzing data density.

## Baselines

Always create simple baselines first.

Examples:

- Previous period
- Moving average
- Seasonal baseline

Advanced models must beat meaningful baselines.

## Evaluation

Use chronological train/validation/test splits.

Do not randomly split time-series data.

Possible metrics:

- MAE
- RMSE
- WAPE

---

# 20. Statistical Analysis

Use statistics where appropriate.

Potential questions:

- Are late deliveries associated with worse reviews?
- Are review distributions different for late vs on-time orders?
- Does freight burden differ by region?
- Do customer segments have materially different AOV?
- Are seller performance differences statistically meaningful?

Potential techniques:

- Confidence intervals
- Hypothesis tests
- Effect sizes
- Correlation
- Non-parametric tests

Do not confuse correlation with causation.

---

# 21. Decision Center

CommerceLens should not stop at describing metrics.

It should convert analysis into decision support.

Recommended structure:

## Issue

What problem exists?

## Evidence

What data supports the observation?

## Business Impact

Why does it matter?

## Likely Contributors

What factors are associated with it?

## Recommended Action

What operational/business action should be considered?

## Confidence

Possible levels:

- High
- Medium
- Exploratory

Recommendations should initially be rule-based and data-derived.

Do not add an LLM solely for marketing purposes.

---

# 22. Technology Stack

## Data / Data Science

- Python
- pandas
- NumPy
- SciPy
- scikit-learn
- Matplotlib
- Jupyter

Additional libraries only when justified.

## Analytics Engineering

- PostgreSQL
- SQL
- dbt
- Pandera
- GitHub Actions

## Backend

- FastAPI
- Pydantic
- SQLAlchemy or an appropriate PostgreSQL access layer
- Uvicorn

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- ECharts or Recharts

## Database / Cloud

Preferred platform:

- Supabase PostgreSQL

## Deployment

Likely architecture:

Frontend:
- Vercel

Backend:
- Render or Railway

Database:
- Supabase PostgreSQL

Final hosting choices can be changed if technical or pricing constraints justify it.

---

# 23. API Design

Potential API routes:

- `/api/v1/kpis`
- `/api/v1/sales`
- `/api/v1/products`
- `/api/v1/customers`
- `/api/v1/cohorts`
- `/api/v1/segments`
- `/api/v1/logistics`
- `/api/v1/sellers`
- `/api/v1/predictions/delivery-risk`
- `/api/v1/forecast`
- `/api/v1/insights`

Exact endpoints can evolve.

---

# 24. Application Navigation

Proposed structure:

CommerceLens

- Overview
- Sales
  - Trends
  - Categories
  - Geography
- Customers
  - Customer Analytics
  - Cohorts
  - Segments
- Operations
  - Delivery
  - Sellers
  - Satisfaction
- Predict
  - Delivery Risk
  - Demand Forecast
- Decision Center
- About
  - Data
  - Methodology
  - Model Performance

Navigation should use business terminology instead of academic terminology such as "EDA" or "Model 1."

---

# 25. Public Application Requirements

The public demo should:

- Be accessible online
- Require no login
- Be understandable within 20–30 seconds
- Clearly explain what CommerceLens does
- Include an "Explore Demo" action
- Show meaningful analytics immediately
- Include data and methodology information
- Clearly explain limitations

---

# 26. UI Design Principles

The interface should look like a modern analytics SaaS product.

Use:

- Clean hierarchy
- Consistent spacing
- Clear KPI cards
- Useful filters
- Interactive charts
- Tooltips
- Loading states
- Empty states
- Error states
- Responsive layout

Avoid:

- Rainbow dashboards
- 3D charts
- Excessive animation
- Decorative AI elements
- Large walls of text
- Unnecessary chart proliferation

---

# 27. Repository Structure

Target repository structure:

```text
CommerceLens/
│
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── docker-compose.yml
│
├── data/
│   ├── README.md
│   ├── raw/
│   ├── interim/
│   └── samples/
│
├── notebooks/
│
├── src/
│   ├── ingestion/
│   ├── cleaning/
│   ├── validation/
│   ├── features/
│   ├── models/
│   ├── evaluation/
│   └── utils/
│
├── dbt/
│   ├── models/
│   │   ├── staging/
│   │   ├── intermediate/
│   │   └── marts/
│   ├── tests/
│   └── dbt_project.yml
│
├── api/
│   ├── app/
│   │   ├── routes/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   └── tests/
│
├── web/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── public/
│
├── models/
│
├── tests/
│
├── docs/
│   ├── architecture/
│   ├── data_dictionary/
│   ├── decisions/
│   └── screenshots/
│
└── .github/
    └── workflows/
```

Do not create directories merely because they appear here.

Introduce them when needed.

---

# 28. Git Strategy

Use a professional but lightweight Git workflow.

Primary branch:

- `main`

Example feature branches:

- `feat/data-ingestion`
- `feat/customer-dashboard`
- `feat/delivery-model`
- `fix/payment-aggregation`
- `docs/model-card`

Commit messages should describe the change.

Examples:

- `feat: add order-level logistics mart`
- `fix: prevent duplicate GMV after payment join`
- `test: validate delivery timestamp ordering`

Avoid vague commits such as:

- update
- changes
- final
- final-final

---

# 29. Testing Strategy

CommerceLens should include:

## Data Tests

Examples:

- Required columns exist
- IDs are not null
- Expected keys are unique
- Relationships are valid
- Timestamps follow business logic

## dbt Tests

Use:

- not null
- unique
- relationships
- accepted values
- custom tests where necessary

## Python Tests

Test:

- KPI calculations
- Feature functions
- Transformation logic
- Utility functions

## API Tests

Verify:

- Endpoint status codes
- Schemas
- Error handling
- Expected output structure

## Model Tests

Verify:

- Expected feature schema
- Prediction behavior
- Model artifact loading

## Integration Tests

Verify:

Frontend → API → database/model flow.

---

# 30. Data Quality

Create automated data-quality checks after ingestion.

Example report:

Orders loaded: 99,441  
Duplicate IDs: 0  
Invalid timestamps: 3  
Missing delivery dates: 2,965  
Invalid price values: 0

Pipeline status: PASS

Distinguish between:

- legitimate missing data
- data quality errors

---

# 31. Reproducibility

A new developer should be able to understand:

1. Where the source data comes from
2. How to create the environment
3. How to ingest data
4. How transformations run
5. How models are trained
6. How to run the API
7. How to run the frontend
8. How to deploy the system

Requirements:

- Pin important dependencies
- Use environment variables
- Provide `.env.example`
- Control random seeds where relevant
- Avoid hidden notebook-only configuration

---

# 32. Documentation

Eventually create:

- Main README
- Architecture diagram
- Data dictionary
- KPI dictionary
- Data quality documentation
- EDA report
- Model cards
- Architecture decision records
- API documentation
- Screenshots
- Portfolio case study

README should be understandable by recruiters who do not run the project.

---

# 33. ML Standards

Every model must answer:

1. What business problem does this solve?
2. When is the prediction made?
3. What features are available at that time?
4. What is the baseline?
5. What metric defines success?
6. What action will be taken based on the prediction?

If the model has no clear actionability, reconsider whether it belongs in CommerceLens.

---

# 34. Analytics Standards

Every important chart should support:

Data  
→ metric  
→ observation  
→ interpretation  
→ business implication  
→ action

Avoid producing charts simply because a variable exists.

---

# 35. AI-Assisted Development

The developer uses:

- ChatGPT Plus
- ChatGPT/Codex desktop
- GPT integration inside VS Code

These tools should be used as accelerators.

They should assist with:

- Code generation
- Refactoring
- Debugging
- Documentation
- Testing
- SQL
- Architecture
- Review

However, important concepts must remain understandable to the developer.

For important areas such as:

- SQL joins
- data grain
- feature leakage
- ML evaluation
- API design
- database architecture

the reasoning should be explained rather than blindly generating code.

The developer should be able to defend CommerceLens during a technical interview.

---

# 36. Development Roadmap

Each major phase should be treated as a separate implementation workstream.

## Phase 1 — Project Foundation & Environment

Tasks:

- Create repository
- Initialize Git
- Connect GitHub
- Configure Python
- Configure frontend environment
- Establish dependency management
- Create `.gitignore`
- Create `.env.example`
- Create initial README
- Establish architecture decision records
- Build minimal backend/frontend skeleton
- Verify local execution
- Make first clean commit

Exit condition:

A reproducible repository and working local development environment.

---

## Phase 2 — Data Acquisition, Profiling & Quality

Tasks:

- Acquire Olist dataset
- Inventory source files
- Determine table grains
- Determine relationships
- Profile missingness
- Detect anomalies
- Create initial data dictionary
- Implement raw ingestion
- Implement data validation
- Produce data-quality report

Exit condition:

Reliable raw/staging data with documented quality.

---

## Phase 3 — Database, SQL & Analytics Engineering

Tasks:

- Configure PostgreSQL/Supabase
- Load source/staging data
- Configure dbt
- Build staging models
- Build dimensional models
- Build initial marts
- Add dbt tests
- Validate grain
- Fix join duplication risks
- Create reliable analytical queries

Exit condition:

Tested analytical warehouse.

---

## Phase 4 — Exploratory & Business Analysis

Analyze:

- Sales
- Products
- Customers
- Sellers
- Geography
- Payments
- Logistics
- Reviews

Tasks:

- Perform systematic EDA
- Form hypotheses
- Validate business questions
- Identify strongest findings
- Document limitations

Exit condition:

A structured EDA/business findings report.

---

## Phase 5 — KPI & Analytics Layer

Tasks:

- Define KPI dictionary
- Build executive metrics
- Build reusable analytical marts
- Build API-facing query layer
- Validate consistency across dashboards

Exit condition:

CommerceLens has one consistent definition for every major KPI.

---

## Phase 6 — CommerceLens Web MVP

Tasks:

- Build FastAPI
- Build Next.js application shell
- Connect frontend to API
- Connect API to database
- Build Executive Overview
- Build Sales/Product analytics
- Add filters
- Deploy public application

Exit condition:

A live public CommerceLens MVP exists.

This is the first major product milestone.

---

## Phase 7 — Customer Intelligence

Tasks:

- Customer 360
- RFM
- Cohort analysis
- Retention analysis
- Customer segmentation
- Cluster evaluation
- Segment visualization

Exit condition:

Complete Customer Intelligence workspace.

---

## Phase 8 — Predictive Data Science

Build:

### Late Delivery Risk

- Feature engineering
- Baselines
- Model comparison
- Evaluation
- Calibration
- Explainability
- Inference API

### Demand Forecasting

- Time-series preparation
- Baselines
- Candidate models
- Chronological evaluation
- Forecast endpoint
- Forecast visualization

Exit condition:

Defensible production-facing predictive features.

---

## Phase 9 — Decision Intelligence

Tasks:

- Combine analytics and model outputs
- Detect major business issues
- Attach evidence
- Identify associated contributors
- Generate deterministic recommendations
- Add confidence levels
- Build Decision Center UI

Exit condition:

CommerceLens answers not only "what happened?" but also "what should be investigated or acted upon?"

---

## Phase 10 — Production Hardening

Tasks:

- Automated testing
- CI/CD
- Logging
- Performance review
- API validation
- Security review
- Error handling
- Caching if justified
- Deployment improvements
- Monitoring

Exit condition:

Stable public V1.

---

## Phase 11 — Portfolio & Case Study

Tasks:

- Final README
- Architecture diagrams
- Screenshots
- Demo visuals
- Model cards
- KPI dictionary
- Data dictionary
- Technical case study
- Resume bullets
- Interview preparation

Exit condition:

CommerceLens is recruiter-ready.

---

## Phase 12 — V2 / Advanced Features

Only after V1 is stable.

Possible additions:

- User data upload
- Private workspaces
- Authentication
- Schema mapping
- Incremental data simulation
- Advanced anomaly detection
- Additional ML
- Further automation

Do not begin Phase 12 before V1 is complete.

---

# 37. Milestones

## M0 — Foundation

Phases 1–3.

Result:

A professional data platform foundation exists.

## M1 — Analytics MVP

Phases 4–6.

Result:

A publicly accessible CommerceLens product exists.

## M2 — Data Science V1

Phases 7–9.

Result:

Customer intelligence, predictive analytics and decision support exist.

## M3 — Production Portfolio

Phases 10–11.

Result:

A polished, stable, recruiter-ready project.

## M4 — Advanced Product

Phase 12+.

Result:

Optional product expansion.

---

# 38. MVP Definition

CommerceLens reaches MVP when it includes:

- Real Olist dataset
- Data ingestion
- Data cleaning
- PostgreSQL
- Analytical data model
- KPI layer
- FastAPI
- Next.js frontend
- Executive dashboard
- Sales/product analytics
- Filters
- Public deployment

Not required for MVP:

- Customer clustering
- Delivery ML
- Forecasting
- User uploads
- LLM features

---

# 39. V1 Completion Criteria

CommerceLens V1 is complete when users can:

- Open a public URL
- Understand the product quickly
- Explore business KPIs
- Investigate sales and products
- Explore customer analytics
- Explore delivery/logistics
- View customer segmentation
- Use late-delivery prediction
- Inspect demand forecasts
- View business recommendations
- Read methodology
- Understand data limitations
- Inspect model performance
- Review the GitHub repository

---

# 40. Scope-Control Rules

Avoid the following:

- Starting ML before data understanding
- Building everything in notebooks
- Adding deep learning without justification
- Adding LLMs solely for marketing
- Overengineering with unnecessary microservices
- Building user uploads before the core demo
- Blindly copying tutorials
- Leakage
- Random time-series splits
- Inconsistent KPI definitions
- Hiding project limitations
- Producing excessive meaningless charts
- Blind AI-generated code

---

# 41. Project Philosophy

CommerceLens should follow this progression:

Business question  
→ reliable data  
→ defined metrics  
→ analysis  
→ validated insight  
→ predictive capability where useful  
→ business action  
→ deployed product

Technology should serve the business problem.

Do not introduce technology merely to increase the size of the stack.

---

# 42. Expected Portfolio Outcome

The completed project should support a portfolio description similar to:

Designed and deployed CommerceLens, an end-to-end e-commerce analytics and decision-intelligence platform built using approximately 100K anonymized marketplace orders. Developed a PostgreSQL/dbt analytical pipeline, dimensional data models, KPI and customer analytics, cohort and segmentation workflows, delivery-risk prediction and demand forecasting, exposed analytics through FastAPI, and built an interactive Next.js dashboard deployed online.

---

# 43. Technical Interview Goal

By project completion, the developer should be able to explain:

- Why the data model was designed that way
- Why grain matters
- How duplicate aggregation errors were prevented
- How KPI consistency was maintained
- How target leakage was prevented
- Why particular ML metrics were chosen
- Why time-series splits are chronological
- How models were validated
- How frontend, API and database interact
- How the deployment works
- How data quality is tested
- How analytical findings become business actions

---

# 44. Instructions for GPT Work

When operating on CommerceLens:

1. Treat this document as the canonical project plan.
2. Use `D:\My Projects\CommerceLens` as the working directory.
3. Do not redesign the project unless explicitly requested.
4. Work phase by phase.
5. Do not jump to later phases prematurely.
6. Preserve clear separation between raw data, transformations, analytics, ML, API and frontend.
7. Explain important architectural and analytical decisions.
8. Use production-quality naming and project structure.
9. Prefer simple, defensible solutions over unnecessary complexity.
10. Keep the project runnable and reproducible.
11. Test significant functionality.
12. Avoid target leakage and analytical errors.
13. Maintain documentation as the project evolves.
14. Use Git commits with meaningful messages.
15. Ensure the developer understands important implementation decisions.
16. Do not generate a giant finished codebase all at once unless explicitly instructed.
17. Implement iteratively and verify each major step.
18. Preserve project scope unless a documented architecture decision justifies changing it.
19. Record major deviations from this plan.
20. Optimize for both real learning and professional portfolio quality.

---

# 45. Immediate Next Step

Begin:

**CommerceLens — Phase 1: Project Foundation & Environment**

Working directory:

`D:\My Projects\CommerceLens`

Phase 1 should establish:

- Git repository
- GitHub repository
- Python environment
- Frontend environment
- Backend skeleton
- Frontend skeleton
- dependency strategy
- `.gitignore`
- `.env.example`
- README
- architecture decision record structure
- initial project layout
- local startup verification
- first clean commit

Do not begin dataset acquisition until the Phase 1 exit criteria are satisfied.

---

**CommerceLens Master Plan — Source of Truth**

For GPT Work, I recommend pasting the entire block as the first project instruction/context. The most important section for Work itself is **“Instructions for GPT Work”**, while the rest gives it the architecture and scope needed to make good implementation decisions.

---

# Owner addendum — Permanent engineering standards (2026-09-20)

The project owner requires practical professional software-engineering standards in
all phases, architectural decisions, implementation, reviews, deployment decisions,
and documentation. The requirements are defined in
[CommerceLens engineering standards](engineering-standards.md) and are part of this
master plan unless the owner explicitly changes them. They preserve the original
product scope and phase sequence and avoid unnecessary enterprise complexity.

Before Phase 3, complete the [Phase 1–2 engineering audit](engineering-audit-phase-1-2.md),
correct applicable issues, verify the foundation, and document justified exceptions.
From Phase 3 onward, incorporate security, maintainability, tests, performance,
scalability, privacy, accessibility, and production-readiness during development.
Explain significant decisions and record development shortcuts with a clear revisit gate.

The original master-plan text above is retained. Repository instructions in `AGENTS.md`,
the contributor workflow, and the review template make this requirement actionable.
