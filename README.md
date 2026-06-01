# PlaceSeek Questionnaire

Streamlit questionnaire app for manually annotating PlaceSeek street-view retrieval results.

## Run Locally

```powershell
cd web
streamlit run app.py
```

## Switch To A Single Query

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
- `--query_id`: the matching query ID. Query text is loaded from
  `7_QueryTasks/prompt_banks/{query_id}.txt`.

`--clear_images` removes images from the previous questionnaire before copying
the new task images, keeping the GitHub repository small.

## Build A Multi-Query Questionnaire

Use one website for multiple queries by passing multiple `--job` arguments:

```powershell
python PlaceSeek_questionnaire/dataprocess/prepare_multi_from_findtop20.py `
  --job "A3=4_FindTop20/outputs_physical_affective/A3_m5_physical_affective/a3_m5_physical_affective_top20_review_sheet.csv" `
  --job "A4=4_FindTop20/outputs_physical_affective/A4_m5_physical_affective/a4_m5_physical_affective_top20_review_sheet.csv" `
  --clear_images `
  --activate
```

For 9 tasks, repeat `--job QUERY_ID=CSV_PATH` once per task. The app will show
the correct query and requirements for each row.

## Add Supplement Tasks From Final Rankings

Use this when new `Final_Ranking_Tables` are available but previously published
images should not be annotated again:

```powershell
python PlaceSeek_questionnaire/dataprocess/prepare_supplement_from_final_tables.py --activate
```

The script keeps the current `web/annotation_items.csv`, compares each final
ranking row by `query_id + pano_id/yaw`, and only appends unseen images. If a
query already exists online, new rows are published as `QUERY_supplement`; if a
query is completely new, such as `A2`, it is published as `A2`.

## Files

- `web/app.py`: Streamlit annotation app.
- `web/annotation_items.csv`: images and metadata to annotate.
- `web/queries.csv`: query-specific physical and affective requirements.
- `web/question.csv`: generic physical, affective, and overall match questions.
- `web/images/`: copied images used by the app.
- `dataprocess/prepare_from_findtop20.py`: adapter from `4_FindTop20` review sheets.
- `dataprocess/prepare_multi_from_findtop20.py`: multi-query adapter.
- `dataprocess/prepare_supplement_from_final_tables.py`: supplement adapter that
  appends only unannotated final-ranking images.

Results are saved locally under `web/results/` and are ignored by git.
