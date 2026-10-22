package com.adsentinel.crawler;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

public record ElementRecord(
        String url,
        String location,
        @JsonProperty("frame_path") List<String> framePath,
        String text,
        String context,
        Map<String, Object> style,
        Map<String, Double> bbox,
        boolean visible,
        @JsonProperty("hidden_reasons") List<String> hiddenReasons,
        @JsonProperty("frame_url") String frameUrl) {}
