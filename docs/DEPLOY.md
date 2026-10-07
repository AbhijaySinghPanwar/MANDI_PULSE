# Deploying the app on Streamlit Community Cloud

The deployed app reads the committed snapshot in `data/app_snapshot/` (Parquet, about 2.7 MB). It needs **no database, no `.env` and no secrets**. Deployment is free and takes about 10 minutes.

## What the deployment uses

| Setting | Value |
|---|---|
| Repository | `AbhijaySinghPanwar/MANDI_PULSE` |
| Branch | `main` |
| Main file path | `app/Home.py` |
| Python version | **3.11** |
| Dependencies | `app/requirements.txt`. Streamlit Cloud looks for a requirements file next to the main file first, so this one is used instead of the root `pyproject.toml`. It holds only the app's 8 packages, with pinned versions |
| Environment variables | `DATA_BACKEND = "parquet"` (via Secrets, see step 6). Optional: without a `DATABASE_URL` the app already defaults to the snapshot, but setting it makes the choice explicit |

## Before you start (one-time checks)

1. The latest code is pushed to GitHub (`git push`).
2. `data/app_snapshot/` contains 10 `.parquet` files in the GitHub web view. If not, run `python -m mandipulse export --snapshot`, then commit and push.
3. You know whether the repository is **public** or **private**. Both work; a private repo needs one extra permission click (step 3).

## Steps

1. Go to **https://share.streamlit.io** and click **Continue with GitHub**. Sign in with the GitHub account that owns the repository.
2. The first time only, authorise *Streamlit* to access your GitHub account when asked.
3. Private repositories only: when Streamlit asks for access to private repositories, click **Authorize** or **Grant**. You can also do this later under your workspace **Settings → Linked accounts → GitHub**.
4. On your workspace page, click **Create app** (top right). When asked "Do you already have an app?", choose **Yup, I have an app** (deploy from a GitHub repository).
5. Fill in the form:
   - **Repository:** `AbhijaySinghPanwar/MANDI_PULSE`. You can paste `https://github.com/AbhijaySinghPanwar/MANDI_PULSE/blob/main/app/Home.py` into the "Paste GitHub URL" link instead, which fills all three fields.
   - **Branch:** `main`
   - **Main file path:** `app/Home.py`
   - **App URL** (optional): choose a subdomain, e.g. `mandi-pulse`, which gives `https://mandi-pulse.streamlit.app`.
6. Click **Advanced settings**:
   - **Python version:** select **3.11**. The pinned packages, including pandas 3.0, need Python ≥ 3.11.
   - **Secrets:** paste this one line:
     ```toml
     DATA_BACKEND = "parquet"
     ```
     Streamlit exposes top-level secrets as environment variables, which is what the app reads. Do **not** paste anything from your local `.env`; the deployed app needs no database password or API key.
   - Click **Save**.
7. Click **Deploy**. The build log opens on the right. The first build installs the 8 packages and takes about 2–4 minutes. When it finishes, the Home page appears.

## Check the deployed app (2 minutes)

- [ ] Every page shows the banner **"Data as of 31 Oct 2025"**.
- [ ] The sidebar shows the data attribution (Agmarknet / DMI via Kaggle, **GODL-India**, OpenStreetMap).
- [ ] **Best Mandi:** choose Tomato and *Gujarat › Ahmedabad › Ahmedabad*. You should see ₹1,800, "2 of 8", ₹122 and a map.
- [ ] **Price Outlook** shows the chart with the shaded band. **Crash Risk** shows "Confirmed (46)" and "⚠️ To verify (65)".
- [ ] **Methodology** loads all tables.

## Updating the deployed data later

```bash
python -m mandipulse pipeline --snapshot     # or: python -m mandipulse export --snapshot
git add data/app_snapshot && git commit -m "refresh app snapshot" && git push
```

Streamlit Cloud redeploys automatically after each push to `main`. Code changes in `app/` or `src/mandipulse/serving.py` deploy the same way.

## If something goes wrong

| Symptom | Fix |
|---|---|
| Build log: `No matching distribution found for pandas==3.0.6` (or numpy) | The Python version is not 3.11+. Go to the app's **⋮ → Settings → General**, choose Python 3.11 and reboot. (In some Cloud versions the Python version can only be set at creation; then delete the app and redeploy with 3.11.) |
| `FileNotFoundError: …/data/app_snapshot/meta.parquet missing` | The snapshot was not pushed. Run `git ls-files data/app_snapshot` locally; if empty, run `export --snapshot`, commit and push. |
| `RuntimeError: DATABASE_URL is not set` | The app is trying to use Postgres. Set the secret `DATA_BACKEND = "parquet"` (**⋮ → Settings → Secrets**) and reboot. |
| Map shows no background tiles | The CARTO tile server is unreachable from your network; the points and tooltips still work. |
| App goes to sleep after a few days without visitors | This is normal on the free tier. Click **"Yes, get this app back up!"** and it restarts in about 30 s. |

## Running the deployment setup locally (optional)

Exactly what the Cloud runs, without a database:

```bash
python -m venv .venv-app
source .venv-app/bin/activate                # Windows: .venv-app\Scripts\activate
pip install -r app/requirements.txt
DATA_BACKEND=parquet streamlit run app/Home.py
```

On PowerShell: `$env:DATA_BACKEND = "parquet"; streamlit run app/Home.py`.
