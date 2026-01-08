import subprocess
from pathlib import Path

# Static content for the header and non-Python dependencies
HEADER = """THIRD-PARTY SOFTWARE NOTICES

This software includes third-party software components. Below are the license notices for these components.
"""

# ExifTool is a binary we bundle, not a Python package, so we must add it manually.
# We also include the project's own license pointer.
STATIC_NOTICES = """
================================================================================
ExifTool by Phil Harvey
================================================================================
This application bundles the ExifTool executable.
Copyright (c) 2003-2025 Phil Harvey
Website: https://exiftool.org/

ExifTool is free software; you can redistribute it and/or modify it under the same terms as Perl itself.
This application uses ExifTool under the terms of the Artistic License.

The Artistic License 1.0 can be found at: http://dev.perl.org/licenses/artistic.html
"""


def get_production_packages():
    """
    Returns a set of package names that are in the 'main' dependency group.
    Uses `poetry show --only main` to get the list.
    """
    try:
        # Run poetry show to get the list of main dependencies
        result = subprocess.run(
            ["poetry", "show", "--only", "main"],
            capture_output=True,
            text=True,
            check=True,
        )
        packages = set()
        for line in result.stdout.splitlines():
            if line.strip():
                # Line format: name version description
                parts = line.split()
                if parts:
                    packages.add(parts[0].lower())
        return packages
    except subprocess.CalledProcessError as e:
        print(f"Error running poetry show: {e}")
        return set()


def generate_notices():
    output_file = Path("THIRDPARTY_NOTICES.txt")

    print("Generating third-party notices...")

    # 1. Get the list of production packages
    prod_packages = get_production_packages()
    if not prod_packages:
        print(
            "Warning: Could not determine production packages. detailed python licenses might include dev tools."
        )

    # 2. Run pip-licenses
    # We use --format=plain-vertical to get readable text
    # We use --with-authors and --with-urls for better credit
    cmd = [
        "poetry",
        "run",
        "pip-licenses",
        "--format=plain-vertical",
        "--with-authors",
        "--with-urls",
        "--ignore",
        "image-metadata-analyzer",  # Ignore self
    ]

    # If we successfully identified prod packages, we can try to filter.
    # However, pip-licenses lists *installed* packages.
    # If we pass specific packages to pip-licenses via arguments, it limits the output.
    # But pip-licenses --packages PKG only shows those specific ones, not transitive deps?
    # Actually, pip-licenses doesn't have a simple "only these and their deps" flag easily
    # accessible without graph analysis.
    # BUT, `poetry show --only main` DOES include transitive dependencies by default (flat list) unless --tree is used?
    # Let's verify: `poetry show --only main` output usually includes transitive deps?
    # In the previous turn, `poetry show --only main` output:
    # contourpy, cycler, fonttools, kiwisolver, numpy, packaging, pillow, pyparsing, python-dateutil, six...
    # These ARE transitive deps of matplotlib etc.
    # So `poetry show --only main` GIVES US the full list of production modules!

    if prod_packages:
        cmd.append("--packages")
        cmd.extend(sorted(list(prod_packages)))

    try:
        pip_result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        python_licenses = pip_result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running pip-licenses: {e}")
        python_licenses = "Error generating Python dependency licenses."

    # 3. Combine content
    content = HEADER + STATIC_NOTICES + "\n" + python_licenses

    # 4. Write to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Successfully generated {output_file}")


if __name__ == "__main__":
    generate_notices()
