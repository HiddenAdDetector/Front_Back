package com.adsentinel.result;

import java.util.List;

public record SubmissionResult(ResultMeta meta, List<Finding> findings) { }
