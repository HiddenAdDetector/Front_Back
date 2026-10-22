package com.adsentinel.detector;

import com.adsentinel.crawler.ElementRecord;
import com.adsentinel.result.SubmissionResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

@Service
public class DetectorCliService {
    private final ObjectMapper mapper;
    private final String cliPath;

    public DetectorCliService(ObjectMapper mapper,
                              @Value("${detector.cli.path:Detection_Engine/detector/detector_cli.exe}") String cliPath) {
        this.mapper = mapper;
        this.cliPath = cliPath;
    }

    public SubmissionResult runOnce(String entryUrl, String startedAt, List<ElementRecord> elements, int deadlineSec,
                                    Path outDir, Path cancelFile, Consumer<String> log) throws Exception {
        Files.createDirectories(outDir);
        Path input = outDir.resolve("elements.json");
        mapper.writerWithDefaultPrettyPrinter().writeValue(input.toFile(), elements);

        List<String> command = new ArrayList<>();
        Path executable = resolveCliPath();
        if (executable.toString().toLowerCase().endsWith(".py")) {
            command.add(resolvePythonExecutable().toString());
            command.add(executable.toString());
        } else {
            command.add(executable.toString());
        }
        command.add("--input"); command.add(input.toString());
        command.add("--out-dir"); command.add(outDir.toString());
        command.add("--entry-url"); command.add(entryUrl);
        command.add("--started-at"); command.add(startedAt);
        command.add("--cancel-file"); command.add(cancelFile.toString());
        command.add("--deadline-sec"); command.add(Integer.toString(Math.max(1, deadlineSec)));
        command.add("--topic"); command.add("TOPIC");
        command.add("--tool-version"); command.add("1.0.0");

        log.accept("A detector_cli 시작: executable=" + executable + ", elements=" + elements.size() + ", deadline_sec=" + deadlineSec);
        Process process = new ProcessBuilder(command)
                .directory(Path.of(System.getProperty("user.dir")).toFile())
                .redirectErrorStream(true)
                .start();
        Thread outputReader = new Thread(() -> {
            try (var reader = process.inputReader(StandardCharsets.UTF_8)) {
                String line;
                while ((line = reader.readLine()) != null) log.accept("[DETECTOR] " + line);
            } catch (IOException ignored) { }
        }, "detector-cli-output");
        outputReader.setDaemon(true);
        outputReader.start();

        long waitSec = Math.max(10, deadlineSec + 15L);
        boolean finished = process.waitFor(waitSec, TimeUnit.SECONDS);
        if (!finished) {
            log.accept("detector_cli 안전 대기 시간 초과: " + waitSec + "초");
            process.destroy();
            throw new IllegalStateException("detector_cli process timeout");
        }
        outputReader.join(2_000);
        int exitCode = process.exitValue();
        log.accept("A detector_cli 종료 코드: " + exitCode);

        Path resultPath = outDir.resolve("result.json");
        if (!Files.exists(resultPath)) throw new IllegalStateException("detector_cli가 result.json을 생성하지 않았습니다.");
        if (exitCode != 0 && exitCode != 2) throw new IllegalStateException("detector_cli failed with exit code " + exitCode);
        return mapper.readValue(resultPath.toFile(), SubmissionResult.class);
    }

    private Path resolveCliPath() {
        Path configured = Path.of(cliPath);
        if (configured.isAbsolute()) return configured;
        Path workingDirectory = Path.of(System.getProperty("user.dir"));
        Path direct = workingDirectory.resolve(configured).normalize();
        if (Files.exists(direct)) return direct;
        Path parent = workingDirectory.getParent();
        Path parentPath = parent == null ? direct : parent.resolve(configured).normalize();
        if (Files.exists(parentPath)) return parentPath;
        if (parentPath.toString().toLowerCase().endsWith(".py")) {
            String pathText = parentPath.toString();
            Path exe = Path.of(pathText.substring(0, pathText.length() - 3) + ".exe");
            if (Files.exists(exe)) return exe;
        }
        return parentPath;
    }

    private Path resolvePythonExecutable() {
        String configured = System.getenv("PYTHON_EXECUTABLE");
        if (configured != null && !configured.isBlank()) {
            Path path = Path.of(configured);
            if (Files.exists(path)) return path;
        }

        Path workingDirectory = Path.of(System.getProperty("user.dir"));
        List<Path> candidates = List.of(
                workingDirectory.resolve(".venv/Scripts/python.exe"),
                workingDirectory.resolve("../.venv/Scripts/python.exe").normalize(),
                workingDirectory.resolve("venv/Scripts/python.exe")
        );
        for (Path candidate : candidates) if (Files.exists(candidate)) return candidate;
        return Path.of("python");
    }
}
