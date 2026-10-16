export interface ErrorDetail {
  code: string;
  message: string;
  request_id?: string;
  upstream?: unknown;
  upgrade_targets?: string[];
  reset_time?: string;
}

export interface ErrorEnvelope {
  error: ErrorDetail;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
}

export interface SignUpRequest {
  email: string;
  password: string;
  segment: "retail" | "institutional";
  tos_accepted: boolean;
  tos_version?: string;
}

export interface SignUpResponse {
  user_id: string;
  email: string;
  segment: string;
  plan: string;
  requires_email_verification: boolean;
  message: string;
}

export interface UserProfileResponse {
  user_id: string;
  email: string;
  segment: string;
  plan: string;
  role: string;
  status: string;
  tos_accepted_version: string | null;
}

export interface FeatureEntitlementDetail {
  state: string;
  decision: string;
  status: number;
  allowed: boolean;
  remaining_quota: number | null;
  reset_time: string | null;
  upgrade_targets?: string[] | null;
  reason?: string | null;
}

export interface EntitlementsResponse {
  user_id: string;
  plan: string;
  segment: string;
  features: {
    feature1_contagion?: FeatureEntitlementDetail;
    feature2_filings?: FeatureEntitlementDetail;
    feature3_forensic?: FeatureEntitlementDetail;
    [key: string]: FeatureEntitlementDetail | undefined;
  };
}

export interface SubmitVerificationRequest {
  regulator: string;
  registration_number: string;
}

export interface VerificationResponse {
  id: string;
  user_id: string;
  regulator: string;
  registration_number: string;
  status: string;
  review_notes?: string | null;
}

export interface ReviewVerificationRequest {
  action: "approve" | "reject";
  review_notes?: string | null;
}
