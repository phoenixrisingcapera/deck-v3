pub mod actions;
pub mod queries;
pub mod router;
pub mod sidecar;

use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct ApiError {
    pub status: u16,
    pub code: String,
    pub message: String,
}

impl ApiError {
    pub fn not_found(path: &str) -> Self {
        Self {
            status: 404,
            code: "not_found".into(),
            message: format!("No route for {}", path),
        }
    }

    pub fn validation(msg: impl Into<String>) -> Self {
        Self {
            status: 400,
            code: "validation_failed".into(),
            message: msg.into(),
        }
    }

    pub fn internal(msg: impl Into<String>) -> Self {
        Self {
            status: 500,
            code: "internal_error".into(),
            message: msg.into(),
        }
    }
}
