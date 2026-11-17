import zxcvbn from "zxcvbn";
import type { TranslationKey } from "@/lib/translation-helpers";
import { VALIDATION } from "@/app/common/translations";

export interface PasswordPolicy {
  policy: "low" | "medium" | "high" | "custom";
  custom?: {
    minLength: number;
    requireUppercase: boolean;
    requireLowercase: boolean;
    requireDigit: boolean;
    requireSpecial: boolean;
    minStrength?: number;
  };
}

export interface PasswordValidationResult {
  valid: boolean;
  errors: TranslationKey[];
  score: number;
  feedback: string[];
}

export function validatePassword(password: string, policy: PasswordPolicy): PasswordValidationResult {
  const errors: TranslationKey[] = [];
  let score = 0;
  const feedback: string[] = [];

  // Determine rules based on policy
  let minLength = 6;
  let requireUppercase = false;
  let requireLowercase = false;
  let requireDigit = false;
  let requireSpecial = false;
  let minStrength = 0;

  switch (policy.policy) {
    case "low":
      minLength = 6;
      break;
    case "medium":
      minLength = 8;
      requireUppercase = true;
      requireLowercase = true;
      requireDigit = true;
      minStrength = 2;
      break;
    case "high":
      minLength = 10;
      requireUppercase = true;
      requireLowercase = true;
      requireDigit = true;
      requireSpecial = true;
      minStrength = 3;
      break;
    case "custom":
      if (policy.custom) {
        minLength = policy.custom.minLength || 6;
        requireUppercase = policy.custom.requireUppercase || false;
        requireLowercase = policy.custom.requireLowercase || false;
        requireDigit = policy.custom.requireDigit || false;
        requireSpecial = policy.custom.requireSpecial || false;
        minStrength = policy.custom.minStrength || 0;
      }
      break;
    default:
      minLength = 6;
  }

  // Length check
  if (password.length < minLength) {
    errors.push({
      key: VALIDATION.password_min_length.key,
      fallback: `Password must be at least ${minLength} characters long.`,
    });
  }

  // Character class checks
  if (requireUppercase && !/[A-Z]/.test(password)) {
    errors.push(VALIDATION.password_require_uppercase);
  }
  if (requireLowercase && !/[a-z]/.test(password)) {
    errors.push(VALIDATION.password_require_lowercase);
  }
  if (requireDigit && !/\d/.test(password)) {
    errors.push(VALIDATION.password_require_digit);
  }
  if (requireSpecial && !/[^a-zA-Z0-9]/.test(password)) {
    errors.push(VALIDATION.password_require_special);
  }

  // zxcvbn strength check
  if (password.length > 0) {
    const result = zxcvbn(password);
    score = result.score;
    if (score < minStrength) {
      errors.push(VALIDATION.password_too_weak);
      if (result.feedback.warning) {
        feedback.push(result.feedback.warning);
      }
      if (result.feedback.suggestions && result.feedback.suggestions.length > 0) {
        feedback.push(...result.feedback.suggestions);
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    score,
    feedback,
  };
}