package com.adsentinel.detector;

import com.adsentinel.crawler.ElementRecord;
import com.adsentinel.result.Finding;
import java.util.List;

public interface Detector {
    List<Finding> detect(List<ElementRecord> elements);
}
