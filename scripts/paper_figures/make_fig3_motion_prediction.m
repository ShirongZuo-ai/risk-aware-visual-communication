%% MAKE_FIG3_MOTION_PREDICTION Authoritative paper Fig. 3 from frozen M2 artifacts.
% This script does not run Webots or alter experiment results. It verifies
% the reported stable-window ADE values from the original per-window result
% artifact and plots only logged ground-truth coordinates. The two predicted
% curves are deterministic outputs of the unchanged M2 kinematic predictor.

clearvars;
close all;

scriptDir = fileparts(mfilename('fullpath'));
repoRoot = fileparts(fileparts(scriptDir));

inPlaceWindowPath = fullfile(repoRoot, 'results', 'm2_trajectory', ...
    'window_results.csv');
inPlaceSummaryPath = fullfile(repoRoot, 'results', 'm2_trajectory', ...
    'summary_metrics.csv');
arcWindowPath = fullfile(repoRoot, 'results', 'm2_trajectory_arc', ...
    'window_results.csv');
arcEpisodePath = fullfile(repoRoot, 'data', 'logs', 'm2', ...
    'trajectory_validation_episode_0002.csv');
outputDir = fullfile(repoRoot, 'figures');

requiredPaths = {inPlaceWindowPath, inPlaceSummaryPath, arcWindowPath, arcEpisodePath};
for pathIndex = 1:numel(requiredPaths)
    assert(isfile(requiredPaths{pathIndex}), 'Missing required artifact: %s', ...
        requiredPaths{pathIndex});
end
if ~isfolder(outputDir)
    mkdir(outputDir);
end

%% Verify the four reported ADE values from the original per-window rows.
windowRows = readtable(inPlaceWindowPath, 'TextType', 'string', ...
    'VariableNamingRule', 'preserve');
summaryRows = readtable(inPlaceSummaryPath, 'TextType', 'string', ...
    'VariableNamingRule', 'preserve');

methods = ["state_only", "command_conditioned"];
horizons = [0.5, 2.0];
verifiedAde = nan(numel(methods), numel(horizons));
verifiedCounts = zeros(numel(methods), numel(horizons));

for methodIndex = 1:numel(methods)
    for horizonIndex = 1:numel(horizons)
        isSelected = windowRows.method == methods(methodIndex) & ...
            abs(windowRows.horizon_s - horizons(horizonIndex)) < 1e-12 & ...
            startsWith(windowRows.category, "stable_");
        selectedAde = windowRows.ade_m(isSelected);
        assert(~isempty(selectedAde), ...
            'No stable-window rows for %s at %.1f s.', ...
            methods(methodIndex), horizons(horizonIndex));
        verifiedAde(methodIndex, horizonIndex) = mean(selectedAde);
        verifiedCounts(methodIndex, horizonIndex) = nnz(isSelected);

        isSummary = summaryRows.method == methods(methodIndex) & ...
            abs(summaryRows.horizon_s - horizons(horizonIndex)) < 1e-12 & ...
            summaryRows.category == "all_stable";
        assert(nnz(isSummary) == 1, ...
            'Expected one all_stable summary row for %s at %.1f s.', ...
            methods(methodIndex), horizons(horizonIndex));
        assert(abs(verifiedAde(methodIndex, horizonIndex) - ...
            summaryRows.ade_mean_m(isSummary)) <= 5e-10, ...
            'Per-window and summary ADE disagree for %s at %.1f s.', ...
            methods(methodIndex), horizons(horizonIndex));
        assert(verifiedCounts(methodIndex, horizonIndex) == ...
            summaryRows.window_count(isSummary), ...
            'Window count disagrees for %s at %.1f s.', ...
            methods(methodIndex), horizons(horizonIndex));
    end
end

reportedAde = [1.21e-4, 7.16e-4; 6.40e-6, 1.37e-5];
roundedVerified = arrayfun(@(value) str2double(sprintf('%.3g', value)), ...
    verifiedAde);
assert(isequal(roundedVerified, reportedAde), ...
    'Verified ADE values do not reproduce the four reported values.');
assert(isequal(verifiedCounts, [439, 251; 439, 251]), ...
    'Stable-window counts do not match the historical evaluation.');
descriptiveRatios = [18.9, 52.3];
roundedRatios = round(reportedAde(1, :) ./ reportedAde(2, :), 1);
assert(isequal(roundedRatios, descriptiveRatios), ...
    'Descriptive ADE ratios do not match the reported rounded values.');

%% Select the historical evaluator's representative forward-arc transition.
arcWindowRows = readtable(arcWindowPath, 'TextType', 'string', ...
    'VariableNamingRule', 'preserve');
isCandidate = arcWindowRows.method == "command_conditioned" & ...
    abs(arcWindowRows.horizon_s - 2.0) < 1e-12 & ...
    arcWindowRows.category == ...
    "transition_forward_left_arc_to_forward_right_arc";
candidateRows = arcWindowRows(isCandidate, :);
assert(height(candidateRows) > 0, 'No representative forward-arc candidates.');
representativeIndex = floor(height(candidateRows) / 2) + 1;
startTime = candidateRows.start_time_s(representativeIndex);
assert(abs(startTime - 7.168) < 1e-12, ...
    'Representative-window identity changed (expected start 7.168 s).');

episodeRows = readtable(arcEpisodePath, 'TextType', 'string', ...
    'VariableNamingRule', 'preserve');
assert(all(episodeRows.episode_id == "episode_0002"), ...
    'Unexpected representative episode identity.');

horizonS = 2.0;
stepS = 0.032;
timeTolerance = 1e-10;
isLoggedSegment = episodeRows.sim_time_s >= startTime - timeTolerance & ...
    episodeRows.sim_time_s <= startTime + horizonS + timeTolerance;
actualRows = episodeRows(isLoggedSegment, :);
assert(height(actualRows) == 63, ...
    'Expected 63 raw logged samples in representative window.');
assert(any(actualRows.motion_phase == "stable_forward_left_arc") && ...
    any(actualRows.motion_phase == "stable_forward_right_arc"), ...
    'Representative window no longer spans the command transition.');

initialIndex = find(abs(episodeRows.sim_time_s - startTime) < timeTolerance, 1);
assert(~isempty(initialIndex), 'Representative start is not a logged sample.');
x0 = episodeRows.robot_x(initialIndex);
y0 = episodeRows.robot_y(initialIndex);
yaw0 = episodeRows.yaw_rad(initialIndex);

offsets = stepS:stepS:horizonS;
if isempty(offsets) || offsets(end) < horizonS - timeTolerance
    offsets(end + 1) = horizonS; %#ok<SAGROW>
else
    offsets(end) = horizonS;
end

[stateX, stateY] = predictStateOnly(x0, y0, yaw0, ...
    episodeRows.linear_velocity_m_s(initialIndex), ...
    episodeRows.angular_velocity_rad_s(initialIndex), offsets);
[segmentStarts, segmentEnds, leftCommands, rightCommands] = ...
    commandSegmentsFromLog(episodeRows, startTime, horizonS);
[commandX, commandY] = predictCommandConditioned(x0, y0, yaw0, offsets, ...
    segmentStarts, segmentEnds, leftCommands, rightCommands);

%% Render at IEEE two-column width.
stateColor = [0.0000, 0.4470, 0.7410];
commandColor = [0.8500, 0.3250, 0.0980];
truthColor = [0.10, 0.10, 0.10];

figureHandle = figure('Color', 'white', 'Units', 'inches', ...
    'Position', [0.6, 0.6, 7.0, 3.35], 'Renderer', 'painters');
layout = tiledlayout(figureHandle, 1, 2, 'TileSpacing', 'compact', ...
    'Padding', 'compact');

trajectoryAxis = nexttile(layout, 1);
hold(trajectoryAxis, 'on');
truthLine = plot(trajectoryAxis, actualRows.robot_x, actualRows.robot_y, '-', ...
    'Color', truthColor, 'LineWidth', 1.9, ...
    'DisplayName', 'Executed (logged)');
stateTrajectoryX = [x0; stateX(:)];
stateTrajectoryY = [y0; stateY(:)];
commandTrajectoryX = [x0; commandX(:)];
commandTrajectoryY = [y0; commandY(:)];
stateTrajectoryLine = plot(trajectoryAxis, stateTrajectoryX, ...
    stateTrajectoryY, '--o', 'Color', stateColor, 'LineWidth', 1.5, ...
    'MarkerSize', 4, 'MarkerFaceColor', 'white', ...
    'MarkerIndices', 1:12:numel(stateTrajectoryX), ...
    'DisplayName', 'State-only');
commandTrajectoryLine = plot(trajectoryAxis, commandTrajectoryX, ...
    commandTrajectoryY, '-.s', 'Color', commandColor, 'LineWidth', 1.5, ...
    'MarkerSize', 4, 'MarkerFaceColor', 'white', ...
    'MarkerIndices', 1:12:numel(commandTrajectoryX), ...
    'DisplayName', 'Command-conditioned');

switchIndex = find(actualRows.motion_phase == "stable_forward_right_arc", 1);
plot(trajectoryAxis, actualRows.robot_x(switchIndex), ...
    actualRows.robot_y(switchIndex), 'd', 'Color', truthColor, ...
    'MarkerFaceColor', 'white', 'MarkerSize', 6, 'LineWidth', 1.1, ...
    'HandleVisibility', 'off');
text(trajectoryAxis, actualRows.robot_x(switchIndex), ...
    actualRows.robot_y(switchIndex), '  command switch', ...
    'FontName', 'Times New Roman', 'FontSize', 8, ...
    'VerticalAlignment', 'bottom', 'Color', [0.25, 0.25, 0.25]);

allTrajectoryX = [actualRows.robot_x; x0; stateX(:); commandX(:)];
allTrajectoryY = [actualRows.robot_y; y0; stateY(:); commandY(:)];
physicalSpan = 1.10 * max(range(allTrajectoryX), range(allTrajectoryY));
centerX = 0.5 * (min(allTrajectoryX) + max(allTrajectoryX));
centerY = 0.5 * (min(allTrajectoryY) + max(allTrajectoryY));
xlim(trajectoryAxis, centerX + 0.5 * physicalSpan * [-1, 1]);
ylim(trajectoryAxis, centerY + 0.5 * physicalSpan * [-1, 1]);
axis(trajectoryAxis, 'equal');
grid(trajectoryAxis, 'on');
box(trajectoryAxis, 'on');
xlabel(trajectoryAxis, 'x position (m)');
ylabel(trajectoryAxis, 'y position (m)');
title(trajectoryAxis, 'Representative trajectory around a command switch', ...
    'FontWeight', 'normal', 'FontSize', 9);
text(trajectoryAxis, 0.02, 0.98, '(a)', 'Units', 'normalized', ...
    'FontName', 'Times New Roman', 'FontSize', 9, 'FontWeight', 'bold', ...
    'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');

adeAxis = nexttile(layout, 2);
hold(adeAxis, 'on');
stateLine = semilogy(adeAxis, horizons, verifiedAde(1, :), '--o', ...
    'Color', stateColor, 'LineWidth', 1.5, 'MarkerSize', 6, ...
    'MarkerFaceColor', 'white', 'DisplayName', 'State-only');
commandLine = semilogy(adeAxis, horizons, verifiedAde(2, :), '-.s', ...
    'Color', commandColor, 'LineWidth', 1.5, 'MarkerSize', 6, ...
    'MarkerFaceColor', 'white', 'DisplayName', 'Command-conditioned');
set(adeAxis, 'XTick', horizons, 'XTickLabel', {'0.5', '2.0'}, ...
    'YScale', 'log', 'YLim', [3e-6, 2e-3]);
xlim(adeAxis, [0.30, 2.20]);
grid(adeAxis, 'on');
box(adeAxis, 'on');
xlabel(adeAxis, 'Prediction horizon (s)');
ylabel(adeAxis, 'Mean ADE (m, log scale)');
title(adeAxis, 'ADE across prediction horizons', ...
    'FontWeight', 'normal', 'FontSize', 9);
text(adeAxis, 0.02, 0.98, '(b)', 'Units', 'normalized', ...
    'FontName', 'Times New Roman', 'FontSize', 9, 'FontWeight', 'bold', ...
    'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');

valueLabelX = [0.54, 1.98];
stateLabelY = verifiedAde(1, :) .* [1.35, 1.15];
commandLabelY = verifiedAde(2, :) .* [0.78, 0.78];
valueLabelAlignment = {'left', 'right'};
for horizonIndex = 1:numel(horizons)
    text(adeAxis, valueLabelX(horizonIndex), stateLabelY(horizonIndex), ...
        sprintf('%.2e', reportedAde(1, horizonIndex)), ...
        'FontName', 'Times New Roman', 'FontSize', 8, ...
        'Color', stateColor, ...
        'HorizontalAlignment', valueLabelAlignment{horizonIndex}, ...
        'VerticalAlignment', 'middle');
    text(adeAxis, valueLabelX(horizonIndex), commandLabelY(horizonIndex), ...
        sprintf('%.2e', reportedAde(2, horizonIndex)), ...
        'FontName', 'Times New Roman', 'FontSize', 8, ...
        'Color', commandColor, ...
        'HorizontalAlignment', valueLabelAlignment{horizonIndex}, ...
        'VerticalAlignment', 'middle');
end

ratioX = [0.59, 1.92];
ratioAlignment = {'left', 'right'};
for horizonIndex = 1:numel(horizons)
    ratioY = sqrt(verifiedAde(1, horizonIndex) * ...
        verifiedAde(2, horizonIndex));
    text(adeAxis, ratioX(horizonIndex), ratioY, ...
        sprintf('%.1fx lower ADE', descriptiveRatios(horizonIndex)), ...
        'FontName', 'Times New Roman', 'FontSize', 8, ...
        'Color', [0.25, 0.25, 0.25], ...
        'HorizontalAlignment', ratioAlignment{horizonIndex}, ...
        'VerticalAlignment', 'middle', 'BackgroundColor', 'white', ...
        'Margin', 1);
end

sharedLegend = legend(trajectoryAxis, ...
    [truthLine, stateTrajectoryLine, commandTrajectoryLine], ...
    'Orientation', 'horizontal', 'Box', 'off', 'FontSize', 8);
sharedLegend.Layout.Tile = 'south';

allAxes = [trajectoryAxis, adeAxis];
set(allAxes, 'FontName', 'Times New Roman', 'FontSize', 8.2, ...
    'LineWidth', 0.75, 'TickDir', 'out', 'Layer', 'top', ...
    'GridColor', [0.72, 0.72, 0.72], 'GridAlpha', 0.30, ...
    'MinorGridAlpha', 0.10);
set(adeAxis, 'YMinorGrid', 'off');

pdfPath = fullfile(outputDir, 'fig3_motion_prediction.pdf');
svgPath = fullfile(outputDir, 'fig3_motion_prediction.svg');
pngPath = fullfile(outputDir, 'fig3_motion_prediction.png');
exportgraphics(figureHandle, pdfPath, 'ContentType', 'vector', ...
    'BackgroundColor', 'white');
% R2022b exportgraphics does not accept SVG; painters + -dsvg preserves
% axes, text, markers, and trajectories as vector elements.
print(figureHandle, svgPath, '-dsvg', '-painters');
exportgraphics(figureHandle, pngPath, 'Resolution', 600, ...
    'BackgroundColor', 'white');
close(figureHandle);

fprintf('Verified stable-window ADE from %s\n', inPlaceWindowPath);
for horizonIndex = 1:numel(horizons)
    fprintf(['  %.1f s: state-only %.12g (n=%d), ' ...
        'command-conditioned %.12g (n=%d)\n'], horizons(horizonIndex), ...
        verifiedAde(1, horizonIndex), verifiedCounts(1, horizonIndex), ...
        verifiedAde(2, horizonIndex), verifiedCounts(2, horizonIndex));
end
fprintf('Representative episode: episode_0002, start %.3f s, horizon %.1f s\n', ...
    startTime, horizonS);
fprintf('Ground truth: %d directly logged samples (no interpolation)\n', ...
    height(actualRows));
fprintf('Wrote %s\nWrote %s\nWrote %s\n', pdfPath, svgPath, pngPath);

%% Local functions implementing the unchanged M2 predictor.
function [xValues, yValues] = predictStateOnly(x0, y0, yaw0, v, omega, offsets)
    xValues = zeros(size(offsets));
    yValues = zeros(size(offsets));
    for index = 1:numel(offsets)
        [xValues(index), yValues(index), ~] = integrateTwist( ...
            x0, y0, yaw0, v, omega, offsets(index));
    end
end

function [segmentStarts, segmentEnds, leftCommands, rightCommands] = ...
        commandSegmentsFromLog(rows, startTime, horizonS)
    left = rows.left_wheel_command_rad_s;
    right = rows.right_wheel_command_rad_s;
    changeIndices = find(abs(diff(left)) > 1e-12 | abs(diff(right)) > 1e-12) + 1;
    changeIndices = changeIndices(rows.sim_time_s(changeIndices) > startTime + 1e-12 & ...
        rows.sim_time_s(changeIndices) < startTime + horizonS - 1e-12);

    segmentStarts = [0; rows.sim_time_s(changeIndices) - startTime];
    segmentEnds = [segmentStarts(2:end); horizonS];
    sourceIndices = zeros(size(segmentStarts));
    for index = 1:numel(segmentStarts)
        absoluteTime = startTime + segmentStarts(index);
        sourceIndices(index) = find(rows.sim_time_s <= absoluteTime + 1e-12, ...
            1, 'last');
    end
    leftCommands = left(sourceIndices);
    rightCommands = right(sourceIndices);
end

function [xValues, yValues] = predictCommandConditioned(x0, y0, yaw0, ...
        offsets, segmentStarts, segmentEnds, leftCommands, rightCommands)
    wheelRadiusM = 0.02;
    axleLengthM = 0.052;
    xValues = zeros(size(offsets));
    yValues = zeros(size(offsets));
    currentX = x0;
    currentY = y0;
    currentYaw = normalizeAngle(yaw0);
    currentTime = 0.0;

    for targetIndex = 1:numel(offsets)
        targetTime = offsets(targetIndex);
        while currentTime + 1e-12 < targetTime
            segmentIndex = find(segmentStarts <= currentTime + 1e-12 & ...
                segmentEnds > currentTime + 1e-12, 1, 'last');
            assert(~isempty(segmentIndex), ...
                'No logged command segment covers prediction time %.12g.', currentTime);
            nextBoundary = min(targetTime, segmentEnds(segmentIndex));
            dt = nextBoundary - currentTime;
            linearVelocity = wheelRadiusM * 0.5 * ...
                (rightCommands(segmentIndex) + leftCommands(segmentIndex));
            angularVelocity = wheelRadiusM * ...
                (rightCommands(segmentIndex) - leftCommands(segmentIndex)) / axleLengthM;
            [currentX, currentY, currentYaw] = integrateTwist( ...
                currentX, currentY, currentYaw, linearVelocity, angularVelocity, dt);
            currentTime = nextBoundary;
        end
        xValues(targetIndex) = currentX;
        yValues(targetIndex) = currentY;
    end
end

function [nextX, nextY, nextYaw] = integrateTwist(x, y, yaw, v, omega, dt)
    if abs(omega) < 1e-9
        nextX = x + v * cos(yaw) * dt;
        nextY = y + v * sin(yaw) * dt;
        nextYaw = yaw;
    else
        nextYawRaw = yaw + omega * dt;
        radius = v / omega;
        nextX = x + radius * (sin(nextYawRaw) - sin(yaw));
        nextY = y - radius * (cos(nextYawRaw) - cos(yaw));
        nextYaw = nextYawRaw;
    end
    nextYaw = normalizeAngle(nextYaw);
end

function angle = normalizeAngle(angle)
    angle = atan2(sin(angle), cos(angle));
end
