import fitz
import os

def generate_optimized_cv(original_path: str, approved_suggestions: list, user_id: int) -> str:
    """
    BDIOF Vector 1 — Generate Optimized CV
    Takes the original CV, applies all approved suggestions
    by replacing regional terms with global equivalents,
    and saves a new optimized PDF.
    """
    try:
        doc = fitz.open(original_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()

        optimized_text = full_text
        changes_made = []

        for suggestion in approved_suggestions:
            original_term = suggestion.get("original", "")
            global_equivalent = suggestion.get("suggestion", "")
            if original_term and global_equivalent:
                if original_term.lower() in optimized_text.lower():
                    import re
                    optimized_text = re.sub(
                        re.escape(original_term),
                        global_equivalent,
                        optimized_text,
                        flags=re.IGNORECASE
                    )
                    changes_made.append({
                        "original": original_term,
                        "replaced_with": global_equivalent
                    })

        output_path = f"uploads/optimized_{user_id}_cv.pdf"
        new_doc = fitz.open()
        page = new_doc.new_page(width=595, height=842)

        # Header
        page.insert_text(
            (50, 50),
            "EQUITYENGINE — BDIOF OPTIMIZED CV",
            fontsize=10,
            color=(0.1, 0.33, 0.85)
        )
        page.draw_line((50, 62), (545, 62), color=(0.1, 0.33, 0.85), width=1)

        # Optimization notice
        page.insert_text(
            (50, 78),
            f"Optimized by BDIOF · {len(changes_made)} regional terms updated for global ATS visibility",
            fontsize=8,
            color=(0.4, 0.4, 0.4)
        )

        # CV Content
        y_position = 105
        line_height = 13
        max_width = 90

        for line in optimized_text.split('\n'):
            if y_position > 800:
                page = new_doc.new_page(width=595, height=842)
                y_position = 50

            line = line.strip()
            if not line:
                y_position += 6
                continue

            # Word wrap
            words = line.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 <= max_width:
                    current_line += (" " if current_line else "") + word
                else:
                    if current_line:
                        page.insert_text(
                            (50, y_position),
                            current_line,
                            fontsize=9,
                            color=(0.1, 0.1, 0.1)
                        )
                        y_position += line_height
                        if y_position > 800:
                            page = new_doc.new_page(width=595, height=842)
                            y_position = 50
                    current_line = word

            if current_line:
                page.insert_text(
                    (50, y_position),
                    current_line,
                    fontsize=9,
                    color=(0.1, 0.1, 0.1)
                )
                y_position += line_height

        new_doc.save(output_path)
        new_doc.close()

        return output_path, changes_made

    except Exception as e:
        raise Exception(f"CV generation failed: {str(e)}")