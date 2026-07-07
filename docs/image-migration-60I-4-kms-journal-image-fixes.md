# 60-I-4 KMS image path and trade journal image UX fixes

## Purpose

This follow-up verifies the unified image storage paths after 60-I-2 and 60-I-3, clarifies KMS editor image actions, and improves the trade journal image list so large uploaded images appear as thumbnails with a click-to-preview modal.

## Storage Path Verification

The common image service uses these domain folders:

| domain | storage folder |
| --- | --- |
| kms | data/kms_images/{yyyy}/{mm}/ |
| stock_tracking | data/stock_tracking_images/{yyyy}/{mm}/ |
| trade_journal | data/trade_journal_images/{yyyy}/{mm}/ |
| trade_method | data/trade_method_images/{yyyy}/{mm}/ |

The FastAPI static mount serves PROJECT_ROOT/data as /static, so a KMS upload saved to data/kms_images/2026/07/sample_20260707001.png is rendered as /static/kms_images/2026/07/sample_20260707001.png.

## KMS Findings

KMS image upload already called the common upload API, but the toolbar labels were ambiguous.

- The old Image button used the local-image picker/reference path flow.
- The upload button called POST /images/upload but had only generic English labels and no success feedback.
- This made it easy to click the wrong button and then expect a file under data/kms_images.

## KMS Changes

- Replaced the ambiguous editor image button with 이미지 URL.
- 이미지 URL only inserts a user-entered URL into the editor. It does not create files under data/kms_images.
- Renamed the upload action to 이미지 업로드.
- 이미지 업로드 selects a local file, calls POST /images/upload with domain=kms, and inserts the returned file_url into the editor.
- Added success feedback showing the returned relative_path, for example data/kms_images/2026/07/....
- Added Korean validation/error messages for unsupported file type, file size, and upload failure.

## Trade Journal UX Changes

- Existing legacy trade journal images and new app_images entries now render as fixed thumbnails in the drawer.
- Thumbnail size is constrained to 180px by 120px on desktop, with object-fit: cover.
- Clicking a thumbnail opens a preview modal.
- Preview modal supports backdrop click, close button, and Escape key close.
- Preview image is constrained with max-width/max-height and object-fit: contain.
- Legacy image delete continues to use the legacy trade journal image API.
- Common app_images delete continues to use DELETE /images/{image_id}.

## Backend And DB Impact

No schema changes were made in 60-I-4.

Backend path mapping already present:

- kms -> data/kms_images
- stock_tracking -> data/stock_tracking_images

## Compatibility

- Existing KMS content is not migrated or deleted.
- Existing trade journal images remain visible.
- Existing trade method and stock tracking behavior is not redesigned in this task.
- TradeTrainingPage.tsx was not changed.

## Remaining Items

- Browser-level verification with a real image upload is still recommended.
- New KMS posts uploaded before a post id exists still store owner_id as empty; post-id backfill remains a later task.
