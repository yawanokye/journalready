
from app.review_release_guard import filter_and_rewrite_release_findings
from app.natural_supervisor_comment import natural_supervisor_comment


def _review(text=''):
    return {
        'summary': {'academic_level': 'Bachelor'},
        '_runtime_context': {'current_paragraphs': [
            {'paragraph': 1, 'chapter_number': 1, 'heading': 'Organization of the Study', 'section_path': ['CHAPTER ONE','Organization of the Study'], 'text': text or 'Chapter Two presents the literature review and conceptual framework.'}
        ]}
    }


def test_definition_of_terms_is_not_mandatory_without_verified_programme_rule():
    rows = [{
        'finding_id': 'X1', 'section': 'Organization of the Study',
        'issue_title': 'Missing Definition of Terms section',
        'assessment': 'Definition of Terms is missing.',
        'required_action': 'Add a Definition of Terms section.',
    }]
    assert filter_and_rewrite_release_findings(rows, _review()) == []


def test_prompt_instruction_does_not_reach_student_comment():
    row = {
        'item': 'Purpose alignment needs attention',
        'assessment': 'The purpose and objectives do not match.',
        'required_action': "State the exact weakness in the cited passage and provide a direct correction grounded in the current study's design, evidence and terminology.",
    }
    text = natural_supervisor_comment(row)
    assert 'State the exact weakness' not in text
    assert 'grounded in the current study' not in text


def test_duplicate_conceptual_link_findings_consolidate():
    rows = [
        {'finding_id':'A','chapter_number':1,'section':'Background of the Study','issue_title':'The background needs a brief conceptual link','assessment':'The link is unclear.','required_action':'Explain how the constructs relate.'},
        {'finding_id':'B','chapter_number':1,'section':'Background of the Study','issue_title':'Missing conceptual framing','assessment':'The constructs are not connected.','required_action':'Define and connect the constructs.'},
    ]
    result = filter_and_rewrite_release_findings(rows, _review('The background discusses several study constructs.'))
    assert len(result) == 1
