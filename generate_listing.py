"""
generate_listing.py — generates a shared metadata file (_metadata.yml)
that contains the navbar structure. Courses reference this via metadata-files
in their _quarto.yml. Website projects use the navbar directly; book projects
get the configuration through metadata inheritance.
"""
import os
import yaml

def generate_site_structure():
    # Setup paths
    notes_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(notes_dir, ".."))
    site_dir = os.path.join(notes_dir, "site")
    site_quarto_path = os.path.join(site_dir, "_quarto.yml")
    root_quarto_path = os.path.join(root_dir, "_quarto.yml")
    metadata_path = os.path.join(root_dir, "_metadata.yml")

    semesters = ["1sem", "2sem", "3sem", "4sem"]
    sem_dict = {
        "1sem": "First Semester",
        "2sem": "Second Semester",
        "3sem": "Third Semester",
        "4sem": "Fourth Semester"
    }

    # Map semester -> list of (course, href)
    sem_to_courses = {sem: [] for sem in semesters}

    # 1. Generate the .qmd include files for the homepage grid
    for sem in semesters:
        sem_path = os.path.join(root_dir, sem)
        qmd_output = os.path.join(site_dir, f"_{sem}_list.qmd")
        links = []

        if os.path.exists(sem_path):
            # Get list of course directories
            courses = sorted([d for d in os.listdir(sem_path)
                              if os.path.isdir(os.path.join(sem_path, d))])

            for course in courses:
                # Check if it's a valid course with a notes folder
                if os.path.exists(os.path.join(sem_path, course, "notes")):
                    # Link paths used in site menu:
                    href = f"/{sem}/{course}/index.html"
                    # For the site homepage include (relative list)
                    rel_link = f"{sem}/{course}/index.html"
                    links.append(f"- [{course}]({rel_link})")
                    # Save for the navbar include
                    sem_to_courses[sem].append({"text": course, "href": href})

        # Write the include files for the homepage (simple markdown list or placeholder)
        os.makedirs(site_dir, exist_ok=True)
        with open(qmd_output, "w", encoding="utf-8") as f:
            f.write("\n".join(links) if links else "*No courses*")

    # 2. Build the nested navbar menu structure for _quarto.yml
    courses_menu = []
    for sem in semesters:
        sem_label = sem_dict.get(sem, sem)
        course_items = sem_to_courses.get(sem, [])
        if course_items:
            # Quarto supports nested menus; create a semester group containing its courses
            courses_menu.append({"text": sem_label, "menu": course_items})
        else:
            # Keep semester label even if empty (optional)
            courses_menu.append({"text": sem_label})

    navbar_left = [
        {"href": "index.qmd", "text": "Home"},
        {"text": "Courses", "menu": courses_menu}
    ]
    navbar_right = [{"icon": "github", "href": "https://github.com/"}]

    # 3. Write shared metadata file that all projects can reference
    shared_metadata = {
        "website": {
            "title": "University Course Portal",
            "navbar": {
                "left": navbar_left,
                "right": navbar_right
            }
        }
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        yaml.dump(shared_metadata, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # 4. Build root-level _quarto.yml for the main website project
    root_config = {
        "project": {
            "type": "website",
            "output-dir": "docs"
        },
        "website": {
            "title": "University Course Portal",
            "navbar": {
                "left": navbar_left,
                "right": navbar_right
            }
        },
        "format": {
            "html": {
                "theme": "cosmo",
                "toc": True
            }
        }
    }

    with open(root_quarto_path, "w", encoding="utf-8") as f:
        yaml.dump(root_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # 5. Also write a site-specific _quarto.yml (keeps output-dir relative to site)
    # This file will not contain the include (root will handle that), but keeps site-specific output-dir
    site_config = {
        "project": {"type": "website", "output-dir": "../docs"},
        "website": {
            "title": "University Course Portal",
            "navbar": {
                "left": navbar_left,
                "right": navbar_right
            }
        },
        "format": {"html": {"theme": "cosmo", "toc": True}}
    }
    with open(site_quarto_path, "w", encoding="utf-8") as f:
        yaml.dump(site_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

if __name__ == "__main__":
    generate_site_structure()