# Detector CLI Drop-in Folder

Place the team A detector files here:

- `detector_cli.exe`
- `CLI_CONTRACT.md`
- `STYLE_KEYS.md`
- `.env` (local only; never commit)

The Spring Boot backend invokes the executable once after crawling:

```text
detector_cli.exe --input elements.json --out-dir output --cancel-file job.cancel --deadline-sec 60
```

The executable must write `result.json` into `--out-dir` and use the agreed exit codes from `CLI_CONTRACT.md`.
