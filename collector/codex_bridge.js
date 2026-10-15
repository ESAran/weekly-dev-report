// Run inside Codex functions.exec, not Node. Set the trusted absolute directory
// first: store('weeklyReportBridge', '/absolute/private-run/bridge').
const directory = load('weeklyReportBridge');
if (typeof directory !== 'string' || !directory.startsWith('/')) throw Error('Set weeklyReportBridge to a private absolute directory.');
const shellQuote = value => "'" + value.replace(/'/g, "'\\''") + "'";
const allowed = new Set(['github_get_profile', 'github_list_repositories', 'github_fetch',
  'gitlab_get_current_user', 'gitlab_list_projects', 'gitlab_list_commits', 'gitlab_get_commit',
  'gitlab_list_commit_diff', 'gitlab_list_project_merge_requests', 'gitlab_list_merge_request_commits']);
const checkScript = "import json,sys; from pathlib import Path; p=Path(sys.argv[1]); r=p/'request.json'; b=json.loads(r.read_text()) if r.exists() else None; print(json.dumps(b) if b and not (p/('response-'+b['batch']+'.json')).exists() else 'null')";
const pending = await tools.exec_command({cmd: 'python3 -c ' + shellQuote(checkScript) + ' ' + shellQuote(directory), max_output_tokens: 30000, login: false});
if (pending.exit_code !== 0) throw Error('Cannot read the private bridge request.');
const batch = JSON.parse(pending.output);
if (!batch) {
  text({state: 'idle', message: 'No unanswered batch. Check the collector process before retrying.'});
} else {
  if (!/^[a-f0-9]{64}$/.test(batch.batch)) throw Error('Invalid batch ID.');
  const responses = [];
  for (let offset = 0; offset < batch.requests.length; offset += 6) {
    const chunk = batch.requests.slice(offset, offset + 6);
    const results = await Promise.allSettled(chunk.map(async request => {
      if (!/^[a-f0-9]{64}$/.test(request.id) || !allowed.has(request.tool)) throw Error('Operation is outside the read-only allowlist.');
      if (request.tool === 'github_fetch' && !/^https:\/\/api\.github\.com\/repos\//.test(request.arguments.url)) throw Error('URL outside approved repository GET resources.');
      return await tools['mcp__codex_apps__' + request.tool](request.arguments);
    }));
    results.forEach((result, index) => {
      const id = chunk[index].id;
      if (result.status === 'rejected') responses.push({id, error: String(result.reason).slice(0, 2000)});
      else if (result.value.isError) responses.push({id, error: JSON.stringify(result.value.content).slice(0, 2000)});
      else responses.push({id, result: result.value.structuredContent || result.value});
    });
  }
  const temporary = directory + '/response-' + batch.batch + '.json.tmp';
  const target = directory + '/response-' + batch.batch + '.json';
  const result = await tools.apply_patch('*** Begin Patch\n*** Add File: ' + temporary + '\n+' + JSON.stringify({batch: batch.batch, responses}) + '\n*** End Patch');
  if (result?.isError) throw Error('Unable to write bridge response.');
  const publishScript = 'import os,sys; os.chmod(sys.argv[1],0o600); os.replace(sys.argv[1],sys.argv[2])';
  const published = await tools.exec_command({cmd: 'python3 -c ' + shellQuote(publishScript) + ' ' + shellQuote(temporary) + ' ' + shellQuote(target), login: false, max_output_tokens: 1000});
  if (published.exit_code !== 0) throw Error('Unable to finalize bridge response.');
  text({state: 'answered', requests: responses.length, failures: responses.filter(r => r.error).length});
}
