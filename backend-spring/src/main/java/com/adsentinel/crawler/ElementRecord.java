package com.adsentinel.crawler;

import java.util.List;
import java.util.Map;

public record ElementRecord(String url, String location, List<String> framePath, String text, String context, Map<String, Object> style, Map<String, Double> bbox, boolean visible, List<String> hiddenReasons, String frameUrl) {}
