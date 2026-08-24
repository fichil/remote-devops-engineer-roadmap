# Linux File Search Runbook

## Purpose

The purpose of this runbook is to rerun file-search commands and safe file operations.
The sandbox will not change real files.

## Sandbox Setup

```bash
lab=$(mktemp -d /tmp/devops-runbook-20260808.XXXXXX)
cd "$lab"
pwd
mkdir -p "$lab/logs/archive"
mkdir -p "$lab/docs"
mkdir -p "$lab/archive/nested"
printf "File search guide\n" > "$lab/docs/guide.txt"
printf "hidden note\n" > "$lab/docs/.hidden-note.txt"
printf "temporary\n" > "$lab/archive/delete-me.tmp"
printf "keep\n" > "$lab/archive/keep.txt"
printf "nested temporary\n" > "$lab/archive/nested/keep.tmp"
printf "ERROR old failure\n" > "$lab/logs/archive/old.log"
printf "INFO start\nERROR disk full\nerror retry\nINFO done\n" > "$lab/logs/app.log"
```
mktemp -d creates a temporary directory, and lab stores this temp path.
