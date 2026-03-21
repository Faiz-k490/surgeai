# Chunk 2 Clarification Needed

This plan will implement only the Chunk 2 data layer changes for `surgeon-hud` after one scope confirmation.

- Confirm whether `src/App.jsx` should be reduced to **only** wrapping current content in `<SocketManager>` for this chunk, or if existing Chunk 3/4 UI imports/components should remain as-is.
- Once confirmed, implement/store verification will proceed against these files:
  - `src/store/useHudStore.js`
  - `src/providers/SocketManager.jsx`
  - `src/App.jsx`
- Validate event mapping (`step_update`, `warning`, `clear`, `qa_update`, `system_health`) and QA auto-clear timer.
- Run a quick build check and report exact verification results.
