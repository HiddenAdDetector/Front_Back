package com.adsentinel.result;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record Finding(String id, String url, boolean is_violation, String location, String evidence_text, String technique, String extra_finding) {
    public Finding(String id, String url, boolean isViolation, String location, String evidenceText, String technique) {
        this(id, url, isViolation, location, evidenceText, technique, null);
    }
}
