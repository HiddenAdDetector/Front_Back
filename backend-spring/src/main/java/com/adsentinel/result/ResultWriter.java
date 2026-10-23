package com.adsentinel.result;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

@Component
public class ResultWriter {
    private final ObjectMapper mapper;
    public ResultWriter(ObjectMapper mapper) { this.mapper = mapper; }

    public void writeReport(Map<String, Object> report, Path outputDir) throws IOException {
        Files.createDirectories(outputDir);
        mapper.writerWithDefaultPrettyPrinter().writeValue(outputDir.resolve("report.json").toFile(), report);
    }
}
