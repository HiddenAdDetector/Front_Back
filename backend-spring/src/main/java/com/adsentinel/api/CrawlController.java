package com.adsentinel.api;

import com.adsentinel.crawler.CrawlService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = {"http://localhost:5173", "http://127.0.0.1:5173"})
public class CrawlController {
    private final CrawlService service;
    public CrawlController(CrawlService service) { this.service = service; }

    @GetMapping("/health")
    public Map<String, String> health() { return Map.of("status", "ok", "service", "adsentinel-spring"); }

    @PostMapping("/crawl")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public Map<String, String> start(@RequestBody CrawlRequest request) { return Map.of("job_id", service.start(request.url())); }

    @GetMapping("/crawl/{id}")
    public Map<String, Object> status(@PathVariable String id) { return service.status(id); }

    @PostMapping("/crawl/{id}/stop")
    public Map<String, String> stop(@PathVariable String id) { service.stop(id); return Map.of("status", "stopping"); }

    public record CrawlRequest(String url) {}
}
