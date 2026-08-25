"""
Curated technical skill taxonomy used by the CV pipeline's skill
extraction (via spaCy PhraseMatcher) and, later, by the job-posting
required_skills matching logic.

This is intentionally a maintained list rather than relying on spaCy's
default NER, because en_core_web_sm has no built-in concept of
"technical skill" as an entity type — it only recognises general
categories like PERSON, ORG, GPE. A curated list is also more
transparent and auditable for the bias-audit purpose of this project:
you can show an examiner exactly what the system does and does not
recognise as a skill, which matters for a project about visibility gaps.

Extend this list as needed — it does not need to be exhaustive to be
useful, and an incomplete list is a normal, disclosable limitation
(see Chapter 5).
"""

SKILL_TAXONOMY = {
    "Languages": [
        "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go",
        "Rust", "PHP", "Ruby", "Swift", "Kotlin", "SQL", "R", "Dart", "Scala",
    ],
    "Frontend": [
        "React", "Vue.js", "Angular", "Next.js", "Svelte", "HTML", "CSS",
        "Tailwind CSS", "Redux", "jQuery", "Bootstrap",
    ],
    "Backend": [
        "Node.js", "Express.js", "Django", "Flask", "FastAPI", "Spring Boot",
        "Ruby on Rails", "Laravel", "ASP.NET", "NestJS",
    ],
    "Databases": [
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "Firebase",
        "DynamoDB", "Cassandra", "Oracle Database", "MS SQL Server",
    ],
    "Cloud & DevOps": [
        "AWS", "Azure", "Google Cloud Platform", "Docker", "Kubernetes",
        "CI/CD", "Jenkins", "GitHub Actions", "Terraform", "Ansible", "Nginx",
    ],
    "Data & AI": [
        "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch",
        "Pandas", "NumPy", "Scikit-learn", "Data Analysis", "NLP",
        "Computer Vision", "spaCy", "Sentence Transformers",
    ],
    "Mobile": [
        "React Native", "Flutter", "Android Development", "iOS Development", "SwiftUI",
    ],
    "Tools & Practices": [
        "Git", "Agile", "Scrum", "REST API", "GraphQL", "Microservices",
        "Unit Testing", "Test-Driven Development", "Linux", "WebSocket",
        "OAuth", "JWT",
    ],
}

# Flattened lookup: lowercase skill text -> canonical display form.
# Built once at import time and reused by the NLP matcher.
SKILL_LOOKUP = {
    skill.lower(): skill
    for category in SKILL_TAXONOMY.values()
    for skill in category
}

ALL_SKILLS = list(SKILL_LOOKUP.values())
