#!/bin/bash

# Get the absolute path of the root directory (one level up from where this script lives)
# This assumes the script is inside the 'Notes' folder
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting global render from: $ROOT_DIR"

# 1. Generate the dynamic links
echo "Updating site metadata..."
python3 "$ROOT_DIR/Notes/generate_listing.py"

# Find all directories named 'notes' that contain a _quarto.yml file
# We exclude the 'Notes/docs' directory to avoid infinite loops or rendering output
find "$ROOT_DIR" -type d -name "notes" | while read -r notes_dir; do
    
    # Check if there is actually a Quarto project file inside
    if [ -f "$notes_dir/_quarto.yml" ]; then
        echo "----------------------------------------------------------"
        echo "Rendering: $notes_dir"
        echo "----------------------------------------------------------"
        
        # Move into the directory to ensure paths in _quarto.yml resolve correctly
        pushd "$notes_dir" > /dev/null
        
        # Run the Quarto render
        quarto render
        
        # Return to the previous directory
        popd > /dev/null
    else
        echo "Skipping $notes_dir: No _quarto.yml found."
    fi
done

# Also render the main site if it exists
if [ -d "$ROOT_DIR/Notes/site" ]; then
    echo "----------------------------------------------------------"
    echo "Rendering main site..."
    echo "----------------------------------------------------------"
    pushd "$ROOT_DIR/Notes/site" > /dev/null
    quarto render
    popd > /dev/null
fi

echo "Done!"