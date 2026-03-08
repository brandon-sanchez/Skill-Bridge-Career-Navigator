"""
 lask application.

The main entry point that has all the routes and brings every thing together including the resume parser, the AI engine and the job search modules. I have the routes validate the input and call the particular service for returing the response.
"""

import os
import json
from datetime import datetime, timezone

from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify
)

from config import Config
from models import db, Profile
from resume_parser import extract_skills, extract_text_from_file
from ai_engine import analyze_gaps, generate_roadmap


def create_app(config_class=Config):
    """
    Creates and configures the Flask application.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    register_routes(app)

    return app


def validate_onboard_form(form_data, has_resume_text):
    """
    Validate the form info being passed and return a list of error messages.
    
    The errors list will be empty if there are no errors, otherwise the list will contain the list of errors.
    """
    errors = []
    if not form_data.get('name', '').strip():
        errors.append('Name is required.')

    email = form_data.get('email', '').strip()
    if not email:
        errors.append('Email is required.')
    elif '@' not in email or '.' not in email.split('@')[-1]:
        errors.append('Please enter a valid email address.')

    if not form_data.get('persona', '').strip():
        errors.append('Please select what best describes you.')

    if not form_data.get('target_role', '').strip():
        errors.append('Please enter your target role.')

    if not has_resume_text:
        errors.append('Please paste your resume text or upload a file.')

    return errors

def register_routes(app):

    @app.route('/')
    def index():
        """Landing page with the onboarding wizard."""
        
        return render_template('index.html')

    @app.route('/onboard', methods=['POST'])
    def onboard():
        """Process the onboarding wizard and create a profile.

        Saves the profile immediately, then redirects to a loading page
        where skill extraction happens asynchronously via the API call.
        """

        resume_text = request.form.get('resume_text', '').strip()

        # ff a file was uploaded, extract the text from it for storage
        resume_file = request.files.get('resume_file')
        if resume_file and resume_file.filename:
            try:
                file_text = extract_text_from_file(resume_file)
                if file_text:
                    resume_text = file_text
            except ValueError as e:
                flash(str(e), 'warning')
            except Exception:
                flash('Could not read the uploaded file. Please try pasting your resume instead.', 'warning')

        # validating
        errors = validate_onboard_form(request.form, bool(resume_text))

        email = request.form.get('email', '').strip()
        if email and Profile.query.filter_by(email=email).first():
            errors.append('A profile with this email already exists.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('index.html'), 400

        # save the profile without skills
        profile = Profile(
            name=request.form['name'].strip(),
            email=email,
            persona=request.form['persona'].strip(),
            resume_text=resume_text,
            target_role=request.form['target_role'].strip(),
        )
        db.session.add(profile)
        db.session.commit()

        # show loading page while skills are extracted
        return render_template('loading.html',
            title=f'Building Profile — {profile.name}',
            heading='Parsing your resume',
            initial_message='Extracting skills from your resume...',
            generate_url=url_for('api_extract_skills', profile_id=profile.id),
            redirect_url=url_for('profile_view', profile_id=profile.id),
            steps=[
                'Reading your resume...',
                'Identifying skills and technologies...',
                'Building your profile...',
            ],
        )

    @app.route('/profile/<int:profile_id>')
    def profile_view(profile_id):
        """Display profile with extracted skills."""
        
        profile = Profile.query.get_or_404(profile_id)
        return render_template('profile.html', profile=profile)

    @app.route('/profile/<int:profile_id>/edit', methods=['GET', 'POST'])
    def profile_edit(profile_id):
        """Edit a profile. If the skills or role change then it clears the previouly saved analysis."""
        
        profile = Profile.query.get_or_404(profile_id)

        if request.method == 'POST':
            new_skills = request.form.get('skills', '').strip()
            new_role = request.form.get('target_role', '').strip()
            new_persona = request.form.get('persona', '').strip()
            new_name = request.form.get('name', '').strip()

            if not new_skills:
                flash('Skills cannot be empty.', 'danger')
                return render_template('profile.html', profile=profile, editing=True)

            # track if the changes are different in terms of skills or if the role changed
            skills_changed = new_skills != profile.extracted_skills
            role_changed = new_role and new_role != profile.target_role

            if new_name:
                profile.name = new_name
            if new_persona:
                profile.persona = new_persona
            profile.extracted_skills = new_skills
            if new_role:
                profile.target_role = new_role

            if skills_changed or role_changed:
                profile.invalidate_analysis()
                flash('Profile updated! Your analysis will be regenerated with the new data.', 'info')
            else:
                flash('Profile updated.', 'success')

            db.session.commit()
            return redirect(url_for('profile_view', profile_id=profile.id))

        return render_template('profile.html', profile=profile, editing=True)

    @app.route('/profile/<int:profile_id>/delete', methods=['POST'])
    def profile_delete(profile_id):
        """Remove a profile completely."""
        
        profile = Profile.query.get_or_404(profile_id)
        db.session.delete(profile)
        db.session.commit()
        flash('Profile deleted.', 'info')
        return redirect(url_for('index'))

    @app.route('/dashboard/<int:profile_id>')
    def dashboard(profile_id):
        """Gap analysis dashboard. Shows loading page on first visit, results after."""

        profile = Profile.query.get_or_404(profile_id)

        # if not generated yet, show the loading page
        if not profile.has_analysis:
            return render_template('loading.html',
                title=f'Gap Analysis — {profile.name}',
                heading='Analyzing your skills',
                initial_message='Comparing your profile against market demand...',
                generate_url=url_for('api_generate_analysis', profile_id=profile.id),
                redirect_url=url_for('dashboard', profile_id=profile.id),
                steps=[
                    'Fetching job market data...',
                    'Comparing your skills...',
                    'Identifying gaps...',
                    'Building your report...',
                ],
            )

        gap_analysis = json.loads(profile.gap_analysis_json)
        return render_template('dashboard.html', profile=profile, gap=gap_analysis)

    @app.route('/roadmap/<int:profile_id>')
    def roadmap(profile_id):
        """Learning roadmap. Shows loading page while generating."""

        profile = Profile.query.get_or_404(profile_id)

        if not profile.has_analysis:
            return redirect(url_for('dashboard', profile_id=profile.id))

        if not profile.has_roadmap:
            return render_template('loading.html',
                title=f'Learning Roadmap — {profile.name}',
                heading='Getting your roadmap ready',
                initial_message='Building a personalized learning plan just for you...',
                generate_url=url_for('api_generate_roadmap', profile_id=profile.id),
                redirect_url=url_for('roadmap', profile_id=profile.id),
                steps=[
                    'Analyzing your skill gaps...',
                    'Finding the best resources...',
                    'Organizing into phases...',
                    'Finalizing your roadmap...',
                ],
            )

        roadmap_data = json.loads(profile.roadmap_json)
        return render_template('roadmap.html', profile=profile, roadmap=roadmap_data)

    @app.route('/dashboard/<int:profile_id>/refresh', methods=['POST'])
    def dashboard_refresh(profile_id):
        """Regenerate the gap analysis with the latest job posting data."""

        profile = Profile.query.get_or_404(profile_id)
        profile.invalidate_analysis()
        db.session.commit()
        flash('Refreshing analysis with the latest data...', 'info')
        return redirect(url_for('dashboard', profile_id=profile.id))

    @app.route('/api/profile/<int:profile_id>/extract-skills', methods=['POST'])
    def api_extract_skills(profile_id):
        """Extract skills from stored resume text. Called by the loading page after onboarding."""

        profile = Profile.query.get_or_404(profile_id)

        # already extracted
        if profile.get_skills_list():
            return jsonify({'status': 'ready'})

        try:
            skill_data = extract_skills(
                profile.resume_text,
                app.config.get('OPENAI_API_KEY', ''),
            )
            profile.set_skills_list(skill_data.get('skills', []))
            db.session.commit()
            return jsonify({'status': 'ready'})
        except Exception as e:
            app.logger.exception('Skill extraction failed')
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/dashboard/<int:profile_id>/generate', methods=['POST'])
    def api_generate_analysis(profile_id):
        """Generate gap analysis and return JSON status. Called by the loading page."""

        profile = Profile.query.get_or_404(profile_id)

        if profile.has_analysis:
            return jsonify({'status': 'ready'})

        try:
            gap_data = analyze_gaps(
                user_skills=profile.get_skills_list(),
                target_role=profile.target_role,
                persona=profile.persona,
                openai_key=app.config.get('OPENAI_API_KEY', ''),
                rapidapi_key=app.config.get('RAPIDAPI_KEY', ''),
            )
            profile.gap_analysis_json = json.dumps(gap_data)
            profile.analysis_generated_at = datetime.now(timezone.utc)
            db.session.commit()
            return jsonify({'status': 'ready'})
        except Exception as e:
            app.logger.exception('Gap analysis generation failed')
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/roadmap/<int:profile_id>/generate', methods=['POST'])
    def api_generate_roadmap(profile_id):
        """Generate learning roadmap and return JSON status. Called by the loading page."""

        profile = Profile.query.get_or_404(profile_id)

        if not profile.has_analysis:
            return jsonify({'status': 'error', 'message': 'Gap analysis must be completed first.'}), 400

        if profile.has_roadmap:
            return jsonify({'status': 'ready'})

        try:
            gap_analysis = json.loads(profile.gap_analysis_json)
            missing_skills = [
                s.get('skill', s) if isinstance(s, dict) else s
                for s in gap_analysis.get('missing_skills', [])
            ]

            roadmap_data = generate_roadmap(
                missing_skills=missing_skills,
                target_role=profile.target_role,
                persona=profile.persona,
                openai_key=app.config.get('OPENAI_API_KEY', ''),
            )
            profile.roadmap_json = json.dumps(roadmap_data)
            db.session.commit()
            return jsonify({'status': 'ready'})
        except Exception as e:
            app.logger.exception('Roadmap generation failed')
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/search')
    def search():
        """
        Search profiles by name, skills, or target role.
        """
        
        query = request.args.get('q', '').strip()

        results = Profile.query
        if query:
            results = results.filter(
                db.or_(
                    Profile.extracted_skills.ilike(f'%{query}%'),
                    Profile.name.ilike(f'%{query}%'),
                    Profile.target_role.ilike(f'%{query}%'),
                )
            )

        results = results.order_by(Profile.created_at.desc()).all()
        return render_template('search.html', profiles=results, query=query)

    @app.route('/api/check-email')
    def api_check_email():
        """
        Check if an email is already in use.

        Returns True if an email is already in use, False otherwise.
        """
        email = request.args.get('email', '').strip()
        if not email:
            return jsonify({'available': False, 'message': 'Email is required.'})
        exists = Profile.query.filter_by(email=email).first() is not None
        if exists:
            return jsonify({'available': False, 'message': 'A profile with this email already exists.'})
        return jsonify({'available': True})

    @app.errorhandler(404)
    def not_found(e):
        return render_template('base.html', error_message='Page not found.'), 404


# creating the app
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)