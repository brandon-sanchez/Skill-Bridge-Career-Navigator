"""
Tests for Skill-Bridge Career Navigator.
"""

from resume_parser import _extract_skills_with_keywords
from ai_engine import _analyze_gaps_fallback

# happy path tests
def test_onboard_creates_profile(client):
    """Submitting valid form data should create a profile and show the loading page"""

    response = client.post('/onboard', data={
        'name': 'Jake Ryan',
        'email': 'jake@su.edu',
        'persona': 'recent_grad',
        'resume_text': (
            'Jake Ryan\n'
            'TECHNICAL SKILLS\n'
            'Languages: Java, Python, C/C++, SQL, JavaScript, HTML/CSS, R\n'
            'Frameworks: React, Node.js, Flask, FastAPI\n'
            'Developer Tools: Git, Docker, TravisCI, Google Cloud Platform\n'
            'Libraries: pandas, NumPy, Matplotlib\n'
        ),
        'target_role': 'Software Engineer',
    })

    # 200 means the loading page was returned successfully
    assert response.status_code == 200
    assert b'Parsing your resume' in response.data
    assert b'Extracting skills from your resume' in response.data


def test_gap_analysis_fallback_returns_correct_structure():
    """The fallback gap analysis should split skills into matched vs missing
    and calculate a strength score — no AI needed.

    Uses skills similar to Jake's resume against a Software Engineer market.
    """

    user_skills = ['Python', 'Flask', 'React', 'Docker', 'Java', 'Git', 'PostgreSQL']

    market_skills = [
        {'skill': 'Python', 'frequency': 90},
        {'skill': 'React', 'frequency': 80},
        {'skill': 'Docker', 'frequency': 70},
        {'skill': 'AWS', 'frequency': 65},
        {'skill': 'Kubernetes', 'frequency': 50},
        {'skill': 'CI/CD', 'frequency': 45},
        {'skill': 'PostgreSQL', 'frequency': 40},
        {'skill': 'Git', 'frequency': 35},
    ]

    result = _analyze_gaps_fallback(
        user_skills=user_skills,
        target_role='Software Engineer',
        persona='recent_grad',
        market_skills=market_skills,
        data_source='test',
        postings_analyzed=10,
    )

    # checking to see that the result has all the expected keys
    assert 'matched_skills' in result
    assert 'missing_skills' in result
    assert 'strength_score' in result
    assert 'summary' in result
    assert result['method'] == 'fallback'
    assert result['data_source'] == 'test'
    assert result['postings_analyzed'] == 10

    matched_names = [s['skill'] for s in result['matched_skills']]
    missing_names = [s['skill'] for s in result['missing_skills']]

    # Python, React, Docker, PostgreSQL, Git should match
    assert 'Python' in matched_names
    assert 'React' in matched_names
    assert 'Docker' in matched_names
    assert 'PostgreSQL' in matched_names
    assert 'Git' in matched_names

    # these keywords should be missing should be missing
    assert 'AWS' in missing_names
    assert 'Kubernetes' in missing_names
    assert 'CI/CD' in missing_names

    # since 5 out of 8 skills should match it should be about 62% as the score
    assert result['strength_score'] == 62

    # each missing skill should have a priority based on its frequency
    missing_by_name = {s['skill']: s for s in result['missing_skills']}
    assert missing_by_name['AWS']['priority'] == 'high'
    assert missing_by_name['Kubernetes']['priority'] == 'medium'
    assert missing_by_name['CI/CD']['priority'] == 'medium'

# edge case tests

def test_onboard_rejects_empty_form(client):
    """Submitting a completely empty form should return errors and not crash"""

    response = client.post('/onboard', data={})

    # should return 400 for a bad request since the validation should catch the missing fields
    assert response.status_code == 400
    assert b'Name is required' in response.data

    # also test with partial data like with no resume or persona being passed in
    response = client.post('/onboard', data={
        'name': 'Jake Ryan',
        'email': 'jake@su.edu',
        'target_role': 'Software Engineer',
    })

    assert response.status_code == 400
    assert b'Please select what best describes you' in response.data
    assert b'Please paste your resume' in response.data


def test_skill_extraction_handles_nonsense_input():
    """
    Passing random text with no real skills should return an empty list,
 and not throw an error.
    """

    result = _extract_skills_with_keywords(
        'Lorem ipsum dolor sit amet, consectetur adipiscing elit. '
        'No technical skills mentioned anywhere in this paragraph.'
    )

    assert result['method'] == 'keyword_matching'
    assert isinstance(result['skills'], list)
    
    # the length for the list should be zero since there are no real skills in the text
    assert len(result['skills']) == 0

    # also test with a real resume snippet to make sure it finds skills
    result = _extract_skills_with_keywords(
        'Languages: Java, Python, SQL, JavaScript\n'
        'Frameworks: React, Node.js, FastAPI\n'
        'Developer Tools: Git, Docker, Google Cloud Platform\n'
        'Libraries: pandas, NumPy\n'
    )

    assert result['method'] == 'keyword_matching'
    assert len(result['skills']) > 0
    assert 'Python' in result['skills']
    assert 'JavaScript' in result['skills']
    assert 'React' in result['skills']
    assert 'Docker' in result['skills']
    assert 'Git' in result['skills']