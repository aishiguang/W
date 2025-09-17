/* eslint-disable @typescript-eslint/no-explicit-any */
declare const d3: any;

type PetriNode = {
  id: string;
  key: string;
  label?: string;
  type: 'place' | 'transition';
  description?: string;
  exclusive_group?: string | null;
};

type PetriEdge = {
  source: string | { id: string };
  target: string | { id: string };
  source_key?: string | null;
  target_key?: string | null;
  weight?: number;
};

type ChoiceGroup = {
  id: string;
  place_id: number | null;
  place_key: string | null;
  place_label: string | null;
  transition_ids: string[];
  transition_keys: string[];
  exclusive_group?: string | null;
};

type ChoiceLink = {
  group_id: string;
  source: string;
  target: string;
};

type PetriGraphResponse = {
  nodes: PetriNode[];
  edges: PetriEdge[];
  choices: ChoiceGroup[];
};

const container = document.getElementById('graph') as HTMLElement | null;
const detailsPanel = document.getElementById('details') as HTMLElement | null;

let svg: any;
let linkGroup: any;
let nodeGroup: any;
let choiceLinkGroup: any;
let simulation: any;

let nodeById: Map<string, any> = new Map();
let transitionChoices: Map<string, ChoiceGroup[]> = new Map();
let choiceGroupMeta: ChoiceGroup[] = [];

const askForm = document.getElementById('ask-form') as HTMLFormElement | null;
const askInput = document.getElementById('ask-input') as HTMLTextAreaElement | null;
const askAnswer = document.getElementById('ask-answer') as HTMLElement | null;
const askSources = document.getElementById('ask-sources') as HTMLElement | null;
const askError = document.getElementById('ask-error') as HTMLElement | null;

const escapeHtml = (value: string | undefined | null): string => {
  if (!value) return '';
  return value.replace(/[&<>"']/g, (char) => {
    switch (char) {
      case '&':
        return '&amp;';
      case '<':
        return '&lt;';
      case '>':
        return '&gt;';
      case '"':
        return '&quot;';
      default:
        return '&#39;';
    }
  });
};

const showDetails = (node: PetriNode): void => {
  if (!detailsPanel) {
    return;
  }
  const title = escapeHtml(node.label || node.key);
  const key = escapeHtml(node.key || '');
  const description = escapeHtml(node.description || 'No description provided.');
  const type = node.type === 'place' ? 'Place - world state' : 'Transition - quest or choice';
  let choiceMarkup = '';
  if (node.type === 'transition') {
    const groups = transitionChoices.get(node.id) ?? [];
    if (groups.length) {
      const sections = groups
        .map((group) => {
          const heading = group.place_label || group.place_key || group.exclusive_group || 'Choice point';
          const placeLabel = escapeHtml(heading || 'Choice point');
          const exclusivity = group.exclusive_group
            ? `<div class="choice-group-note">Group key: <code>${escapeHtml(group.exclusive_group)}</code></div>`
            : '';
          const alternatives = group.transition_ids
            .filter((id) => id !== node.id)
            .map((id) => {
              const targetNode = nodeById.get(id) as PetriNode | undefined;
              const label = escapeHtml((targetNode && (targetNode.label || targetNode.key)) || id);
              return `<li>${label}</li>`;
            });
          const altContent = alternatives.length ? alternatives.join('') : '<li>(No alternative transitions)</li>';
          return `
            <div class="choice-group">
              <div class="choice-group-title">Choice at ${placeLabel}</div>
              ${exclusivity}
              <ul>${altContent}</ul>
            </div>
          `;
        })
        .join('');
      choiceMarkup = `
        <div class="choice-groups">
          <strong>Alternative transitions:</strong>
          ${sections}
        </div>
      `;
    }
  }
  detailsPanel.innerHTML = `
    <h2>${title}</h2>
    <p class="meta">${type}<br />Key: <code>${key}</code></p>
    <p>${description || 'No description provided.'}</p>
    ${choiceMarkup}
  `;
};

const highlight = (activeId: string): void => {
  if (!nodeGroup) {
    return;
  }
  const peerIds = new Set<string>();
  const groups = transitionChoices.get(activeId) ?? [];
  groups.forEach((group) => {
    group.transition_ids.forEach((id) => {
      if (id !== activeId) {
        peerIds.add(id);
      }
    });
  });

  nodeGroup
    .selectAll('.node-shape')
    .classed('selected-shape', (d: PetriNode) => d.id === activeId)
    .classed('choice-peer-shape', (d: PetriNode) => peerIds.has(d.id));

  if (linkGroup) {
    linkGroup
      .selectAll('path')
      .classed('active', (d: PetriEdge) => {
        const source = typeof d.source === 'object' ? (d.source as { id: string }).id : d.source;
        const target = typeof d.target === 'object' ? (d.target as { id: string }).id : d.target;
        return source === activeId || target === activeId;
      });
  }

  if (choiceLinkGroup) {
    const activeGroups = new Set((transitionChoices.get(activeId) ?? []).map((group) => group.id));
    choiceLinkGroup
      .selectAll('path')
      .classed('active', (d: ChoiceLink) => activeGroups.has(d.group_id));
  }
};

const render = (data: PetriGraphResponse): void => {
  if (!container || !detailsPanel) {
    return;
  }

  const nodes = data.nodes.map((d) => ({ ...d }));
  const links = data.edges.map((e) => ({ ...e }));
  const choiceGroupsData = Array.isArray(data.choices) ? data.choices : [];
  const choiceLinksData: ChoiceLink[] = [];

  choiceGroupsData.forEach((group) => {
    if (!group || !Array.isArray(group.transition_ids) || group.transition_ids.length < 2) {
      return;
    }
    for (let i = 0; i < group.transition_ids.length; i += 1) {
      for (let j = i + 1; j < group.transition_ids.length; j += 1) {
        choiceLinksData.push({
          group_id: group.id,
          source: group.transition_ids[i],
          target: group.transition_ids[j],
        });
      }
    }
  });

  let width = container.clientWidth;
  let height = Math.max(560, window.innerHeight - 260);

  d3.select('#graph').selectAll('*').remove();

  svg = d3
    .select('#graph')
    .append('svg')
    .attr('width', width)
    .attr('height', height);

  const defs = svg.append('defs');
  defs
    .append('marker')
    .attr('id', 'arrow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 18)
    .attr('refY', 0)
    .attr('markerWidth', 8)
    .attr('markerHeight', 8)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', 'rgba(157, 171, 204, 0.9)');

  nodeById = new Map(nodes.map((n) => [n.id, n]));

  transitionChoices = new Map();
  choiceGroupMeta = choiceGroupsData;
  choiceGroupsData.forEach((group) => {
    group.transition_ids.forEach((id) => {
      if (!transitionChoices.has(id)) {
        transitionChoices.set(id, []);
      }
      transitionChoices.get(id)!.push(group);
    });
  });

  linkGroup = svg.append('g').attr('class', 'links');
  const link = linkGroup
    .selectAll('path')
    .data(links)
    .enter()
    .append('path')
    .attr('class', 'link')
    .attr('marker-end', 'url(#arrow)');
  link.append('title').text((d: PetriEdge) => {
    const from = d.source_key ? `${d.source_key}` : `${d.source}`;
    const to = d.target_key ? `${d.target_key}` : `${d.target}`;
    return `${from} -> ${to}\nweight: ${d.weight ?? ''}`;
  });

  choiceLinkGroup = svg.append('g').attr('class', 'choice-links');
  const choiceLinks = choiceLinkGroup
    .selectAll('path')
    .data(choiceLinksData, (d: ChoiceLink) => `${d.group_id}-${d.source}-${d.target}`)
    .enter()
    .append('path')
    .attr('class', 'choice-link');

  nodeGroup = svg.append('g').attr('class', 'nodes');
  const node = nodeGroup
    .selectAll('g')
    .data(nodes)
    .enter()
    .append('g')
    .attr('class', 'node')
    .call(
      d3
        .drag()
        .on('start', (event: any, d: any) => {
          if (!event.active) simulation.alphaTarget(0.25).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event: any, d: any) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event: any, d: any) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
    );

  node
    .append((d: PetriNode) =>
      d.type === 'transition'
        ? document.createElementNS('http://www.w3.org/2000/svg', 'rect')
        : document.createElementNS('http://www.w3.org/2000/svg', 'circle')
    )
    .attr('class', (d: PetriNode) => `node-shape ${d.type}`)
    .attr('r', (d: PetriNode) => (d.type === 'place' ? 24 : null))
    .attr('width', (d: PetriNode) => (d.type === 'transition' ? 36 : null))
    .attr('height', (d: PetriNode) => (d.type === 'transition' ? 36 : null))
    .attr('x', (d: PetriNode) => (d.type === 'transition' ? -18 : null))
    .attr('y', (d: PetriNode) => (d.type === 'transition' ? -18 : null))
    .attr('transform', (d: PetriNode) => (d.type === 'transition' ? 'rotate(45)' : null))
    .attr('stroke-linejoin', 'round')
    .on('mouseenter', (_event: any, d: PetriNode) => {
      showDetails(d);
      highlight(d.id);
    })
    .on('click', (_event: any, d: PetriNode) => {
      showDetails(d);
      highlight(d.id);
    });

  node
    .append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', (d: PetriNode) => (d.type === 'place' ? -30 : -26))
    .text((d: PetriNode) => d.label || d.key);

  simulation = d3
    .forceSimulation(nodes)
    .force('link', d3.forceLink(links).id((d: PetriNode) => d.id).distance(140).strength(0.6))
    .force('charge', d3.forceManyBody().strength(-360))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius((d: PetriNode) => (d.type === 'place' ? 46 : 42)).strength(0.9))
    .on('tick', () => {
      nodes.forEach((d: any) => {
        d.x = Math.max(40, Math.min(width - 40, d.x || width / 2));
        d.y = Math.max(40, Math.min(height - 40, d.y || height / 2));
      });

      link.attr('d', (d: any) => {
        const sx = d.source.x;
        const sy = d.source.y;
        const tx = d.target.x;
        const ty = d.target.y;
        return `M${sx},${sy} L${tx},${ty}`;
      });

      choiceLinks.attr('d', (d: ChoiceLink) => {
        const sourceNode = nodeById.get(d.source) as any;
        const targetNode = nodeById.get(d.target) as any;
        if (!sourceNode || !targetNode) {
          return null;
        }
        return `M${sourceNode.x},${sourceNode.y} L${targetNode.x},${targetNode.y}`;
      });

      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

  const handleResize = () => {
    width = container.clientWidth;
    height = Math.max(520, window.innerHeight - 260);
    svg.attr('width', width).attr('height', height);
    simulation.force('center', d3.forceCenter(width / 2, height / 2));
    simulation.alpha(0.3).restart();
  };

  window.addEventListener('resize', handleResize);

  if (nodes.length) {
    showDetails(nodes[0]);
    highlight(nodes[0].id);
  } else {
    detailsPanel.innerHTML = '<div class="status">No Petri-Net nodes found. Seed data first.</div>';
  }
}; 

const fetchGraph = () => {
  if (!detailsPanel) {
    return;
  }
  fetch('/petri/graph/data')
    .then((response) => {
      if (!response.ok) throw new Error('Request failed');
      return response.json();
    })
    .then((data: PetriGraphResponse) => {
      if (!data || !Array.isArray(data.nodes)) {
        throw new Error('Malformed response');
      }
      detailsPanel.innerHTML = '<div class="status">Graph ready. Hover or click any node.</div>';
      render(data);
    })
    .catch((error) => {
      console.error('Failed to load Petri-Net graph', error);
      detailsPanel.innerHTML = '<div class="status">Unable to load graph data. Check that the database is seeded and the API is running.</div>';
    });
};

type AskResponse = {
  answer: string;
  sources?: { id: number; title: string }[];
};

const wireAskPanel = () => {
  if (!askForm || !askInput || !askAnswer || !askSources) {
    return;
  }

  const setLoading = (loading: boolean) => {
    const submit = askForm.querySelector('button[type="submit"]') as HTMLButtonElement | null;
    if (submit) {
      submit.disabled = loading;
      submit.textContent = loading ? 'Thinking…' : 'Ask';
    }
  };

  const resetPanels = () => {
    if (askError) askError.textContent = '';
    askAnswer.textContent = '';
    askSources.textContent = '';
  };

  askForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const question = askInput.value.trim();
    if (!question) {
      return;
    }
    resetPanels();
    if (askAnswer) {
      askAnswer.textContent = 'Fetching answer…';
    }
    setLoading(true);
    fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, depth: 2, max_docs: 12 })
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        return response.json() as Promise<AskResponse>;
      })
      .then((data) => {
        resetPanels();
        if (askAnswer) {
          askAnswer.textContent = data.answer || 'No answer returned.';
        }
        if (askSources && data.sources && data.sources.length) {
          const titles = data.sources.map((s) => escapeHtml(s.title)).join(', ');
          askSources.innerHTML = `Sources: ${titles}`;
        }
      })
      .catch((error) => {
        console.error('Ask endpoint failed', error);
        if (askAnswer) askAnswer.textContent = '';
        if (askError) {
          askError.textContent = 'Unable to fetch answer. Please try again in a moment.';
        }
      })
      .finally(() => {
        setLoading(false);
      });
  });
};

wireAskPanel();
fetchGraph();
