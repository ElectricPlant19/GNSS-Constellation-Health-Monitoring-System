# GitHub Actions workflow to automatically update bundled TLE and GP history data
# Runs weekly and commits updated data files back to the repository

name: Update TLE Data

on:
  # Run every Sunday at 00:00 UTC
  schedule:
    - cron: '0 0 * * 0'
  
  # Allow manual trigger from GitHub UI
  workflow_dispatch:

permissions:
  contents: write  # Explicitly grant write permissions

jobs:
  update-data:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          # Use a token with write permissions
          token: ${{ secrets.GITHUB_TOKEN }}
          fetch-depth: 0  # Fetch full history for proper git operations
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'  # Cache pip dependencies for faster runs
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests pandas numpy
      
      - name: Verify credentials are set
        run: |
          if [ -z "${{ secrets.SPACETRACK_USERNAME }}" ]; then
            echo "ERROR: SPACETRACK_USERNAME secret is not set"
            exit 1
          fi
          if [ -z "${{ secrets.SPACETRACK_PASSWORD }}" ]; then
            echo "ERROR: SPACETRACK_PASSWORD secret is not set"
            echo "Note: Password secret exists but may be empty"
            exit 1
          fi
          echo "✅ Credentials are configured"
      
      - name: Create data directory if needed
        run: |
          mkdir -p data
          echo "Data directory structure:"
          ls -la data/ || echo "data/ directory is empty"
      
      - name: Run update script
        env:
          SPACETRACK_USERNAME: ${{ secrets.SPACETRACK_USERNAME }}
          SPACETRACK_PASSWORD: ${{ secrets.SPACETRACK_PASSWORD }}
        run: |
          echo "Starting data update..."
          python scripts/update_bundled_data.py --days 365 --constellation all
          echo "Update script completed"
      
      - name: Verify data was created
        run: |
          echo "Checking for generated files..."
          ls -lh data/
          if [ -z "$(ls -A data/)" ]; then
            echo "WARNING: No files generated in data/ directory"
            exit 1
          fi
          echo "✅ Data files generated successfully"
      
      - name: Check for changes
        id: check_changes
        run: |
          git add data/
          if git diff --staged --quiet; then
            echo "No changes detected"
            echo "changes=false" >> $GITHUB_OUTPUT
          else
            echo "Changes detected in data directory"
            echo "changes=true" >> $GITHUB_OUTPUT
            git diff --staged --stat
          fi
      
      - name: Configure git
        if: steps.check_changes.outputs.changes == 'true'
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
      
      - name: Commit and push changes
        if: steps.check_changes.outputs.changes == 'true'
        run: |
          git commit -m "🛰️ Auto-update TLE and GP history data [$(date -u +'%Y-%m-%d %H:%M UTC')]"
          git push
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Report status
        if: always()
        run: |
          if [ "${{ steps.check_changes.outputs.changes }}" == "true" ]; then
            echo "✅ Data updated and pushed successfully"
          else
            echo "ℹ️ No changes to commit"
          fi
