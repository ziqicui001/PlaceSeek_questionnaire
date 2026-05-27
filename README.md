# PlaceSeek Questionnaire

Streamlit questionnaire app for manually annotating PlaceSeek street-view retrieval results.

## Run Locally

```powershell
cd web
streamlit run app.py
```

## Switch To A New Query

From the main `lang2img` workspace, regenerate the web input files with:

```powershell
python PlaceSeek_questionnaire/dataprocess/prepare_from_findtop20.py `
  --input_csv "4_FindTop20/outputs_physical_affective/A1_m5_physical_affective/a1_m5_physical_affective_top20_review_sheet.csv" `
  --query_id A1 `
  --clear_images `
  --activate
```

For a different query, only change:

- `--input_csv`: the new `4_FindTop20` review sheet.
- `--query_id`: the matching query ID in `web/queries.csv`.

`--clear_images` removes images from the previous questionnaire before copying
the new task images, keeping the GitHub repository small.

## Files

- `web/app.py`: Streamlit annotation app.
- `web/annotation_items.csv`: images and metadata to annotate.
- `web/queries.csv`: query-specific physical and affective requirements.
- `web/question.csv`: generic physical, affective, and overall match questions.
- `web/images/`: copied images used by the app.
- `dataprocess/prepare_from_findtop20.py`: adapter from `4_FindTop20` review sheets.

Results are saved locally under `web/results/` and are ignored by git.
