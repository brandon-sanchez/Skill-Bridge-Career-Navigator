from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Profile(db.Model):
    """
    Represents a user's career profile including their skills, target role, and cached analysis.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    # persona should somewhat dictate how the AI views their skills
    persona = db.Column(db.String(50), nullable=False)

    # keeping the raw resume text around so users can re-parse if needed
    resume_text = db.Column(db.Text, default='')
    extracted_skills = db.Column(db.Text, nullable=False, default='')

    target_role = db.Column(db.String(100), nullable=False)
    experience_years = db.Column(db.Integer, default=0)

    def __init__(self, name: str = '', email: str = '', persona: str = '',
                 resume_text: str = '', extracted_skills: str = '',
                 target_role: str = '', experience_years: int = 0, **kwargs):
        super().__init__(
            name=name, email=email, persona=persona,
            resume_text=resume_text, extracted_skills=extracted_skills,
            target_role=target_role, experience_years=experience_years,
            **kwargs
        )

    # these will get populated after the first analysis run and stick around until the user changes something meaningful like their skills or target role
    gap_analysis_json = db.Column(db.Text, nullable=True)
    roadmap_json = db.Column(db.Text, nullable=True)
    analysis_generated_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def get_skills_list(self):
        """
        Split the comma-separated skills string into a clean list
        """
        
        if not self.extracted_skills:
            return []
        return [s.strip() for s in self.extracted_skills.split(',') if s.strip()]

    def set_skills_list(self, skills):
        """
        Take a list of skills, deduplicate them, sort alphabetically, and store.
        """
        
        unique = sorted(set(s.strip() for s in skills if s.strip()), key=str.lower)
        self.extracted_skills = ', '.join(unique)

    def invalidate_analysis(self):
        """
        Wipe the cached analysis so it gets regenerated on the next dashboard visit.
        """

        self.gap_analysis_json = None
        self.roadmap_json = None
        self.analysis_generated_at = None

    @property
    def has_analysis(self):
        return self.gap_analysis_json is not None

    @property
    def has_roadmap(self):
        return self.roadmap_json is not None

    @property
    def persona_display(self):
        """Turn internal keys like 'recent_grad' into readable labels like 'Recent Graduate'."""
        
        labels = {
            'recent_grad': 'Recent Graduate',
            'career_switcher': 'Career Switcher',
            'upskilling': 'Upskilling Professional',
            'mentor': 'Mentor / Advisor',
        }
        return labels.get(self.persona, self.persona)

    def __repr__(self):
        return f'<Profile {self.name} - {self.target_role}>'