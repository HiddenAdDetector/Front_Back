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

    public void writeReport(Map<String, Object> report) throws IOException {
        Files.createDirectories(Path.of("output"));
        mapper.writerWithDefaultPrettyPrinter().writeValue(Path.of("output/report.json").toFile(), report);
    }
}
