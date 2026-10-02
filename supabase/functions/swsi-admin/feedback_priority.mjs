export function normalizeFeedbackField(value, max = 80) {
  return typeof value === 'string' ? value.trim().slice(0, max).toLowerCase() : '';
}

const HIGH_CATEGORIES = new Set([
  'answer_question',
  'law_outdated',
]);

const MEDIUM_CATEGORIES = new Set([
  'question_display',
  'explanation_error',
  'theory_question',
  'site_bug',
  'ai_feedback',
  'suggestion',
]);

export function deriveFeedbackPriority(row) {
  const category = normalizeFeedbackField(row && row.category, 60);

  if (HIGH_CATEGORIES.has(category)) {
    return {
      risk_level: 'high',
      confidence: 0.95,
      action: 'needs_review',
      source: 'derived_fallback_v1',
      reason: category === 'law_outdated'
        ? 'legal_content_may_be_stale'
        : 'answer_or_grading_may_be_wrong',
    };
  }

  if (MEDIUM_CATEGORIES.has(category)) {
    return {
      risk_level: 'medium',
      confidence: 0.8,
      action: 'needs_review',
      source: 'derived_fallback_v1',
      reason: 'student_report_requires_product_or_content_review',
    };
  }

  return {
    risk_level: 'untriaged',
    confidence: null,
    action: 'pending_triage',
    source: 'derived_fallback_v1',
    reason: 'insufficient_deterministic_signal',
  };
}
