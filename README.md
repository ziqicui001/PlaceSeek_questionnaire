# PlaceSeek Questionnaire

Streamlit questionnaire app for manually annotating PlaceSeek street-view retrieval results.

## Run Locally

```powershell
cd web
streamlit run app.py
```

## Files

- `web/app.py`: Streamlit annotation app.
- `web/annotation_items.csv`: images and metadata to annotate.
- `web/queries.csv`: query-specific physical and affective requirements.
- `web/question.csv`: generic physical, affective, and overall match questions.
- `web/images/`: copied images used by the app.
- `dataprocess/prepare_from_findtop20.py`: adapter from `4_FindTop20` review sheets.

Results are saved locally under `web/results/` and are ignored by git.
