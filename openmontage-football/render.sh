#!/bin/bash
# Renders the boy-football video using OpenMontage + Remotion
# Run this from inside the OpenMontage directory after make setup

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROPS="$SCRIPT_DIR/boy-football.json"
COMPOSER="remotion-composer"
OUTPUT="projects/boy-football/renders/boy-football.mp4"

# Copy props into the Remotion public directory
mkdir -p "$COMPOSER/public/demo-props"
cp "$PROPS" "$COMPOSER/public/demo-props/boy-football.json"

# Create output directory
mkdir -p projects/boy-football/renders

echo "Rendering boy-football.mp4..."
npx remotion render "$COMPOSER/src/index.tsx" Explainer "$OUTPUT" \
  --props "$COMPOSER/public/demo-props/boy-football.json" \
  --codec h264

echo ""
echo "Done! Video saved to: $OUTPUT"
echo "Open it with: open $OUTPUT"
