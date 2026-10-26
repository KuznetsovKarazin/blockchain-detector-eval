"""Render publication figures from saved aggregate CSVs; never fit models."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

BASE = Path(__file__).resolve().parents[1]
REV = BASE / 'revision1'
OUT = BASE / 'manuscript/figures_revision1'
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.titleweight': 'bold', 'pdf.fonttype': 42,
                     'svg.fonttype': 'none', 'savefig.facecolor': 'white'})
COLORS = ['#0072B2', '#D55E00', '#009E73', '#CC79A7']
INPUTS = {}
CAPTIONS = {}


def read(path):
    path = Path(path)
    INPUTS[str(path.relative_to(BASE))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pd.read_csv(path)


def save(fig, stem, caption):
    fig.savefig(OUT / f'{stem}.pdf', bbox_inches='tight')
    fig.savefig(OUT / f'{stem}.svg', bbox_inches='tight')
    fig.savefig(OUT / f'{stem}.png', dpi=180, bbox_inches='tight')
    plt.close(fig)
    CAPTIONS[stem] = caption


def graph_figures():
    root = REV / 'graph_mechanism/run_20261025_v1'
    curves = read(root / 'component_curves.csv')
    fixed = read(root / 'fixed_test_feasibility.csv')
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.6), layout='constrained')
    for policy, label, color, marker in zip(
        ['project_only', 'clone_only', 'joint'],
        ['Project', 'Lexical clone', 'Project + clone'], COLORS, ['s', '^', 'o']):
        d = curves.query('normalization == "string_aware" and cohort == "full_upstream_21950" and policy == @policy').sort_values('threshold')
        assert len(d) == 13
        axes[0].plot(d.threshold, d.giant_fraction * 100, label=label, color=color, marker=marker, markersize=4)
    axes[0].set(xlabel='Jaccard threshold', ylabel='Largest component (% of 21,457 DAppSCAN files)',
                yscale='log', ylim=(0.1, 110), title='(a) Interaction of dependence relations')
    axes[0].set_yticks([0.1, 1, 10, 100], ['0.1', '1', '10', '100'])
    axes[0].legend(loc='center left', fontsize=9)
    for test, color, marker in [('outside_p90_seed2', COLORS[0], 'o'), ('outside_p90_seed4', COLORS[1], 's')]:
        d = fixed.query('normalization == "string_aware" and cohort == "full_upstream_21950" and policy == "joint" and test_id == @test and `class` == "reentrancy"').sort_values('threshold')
        assert len(d) == 13
        axes[1].plot(d.threshold, d.raw_train_files, color=color, marker=marker, markersize=4, label=f'Test {test[-1]}')
    axes[1].set(xlabel='Jaccard threshold', ylabel='Eligible historical training files',
                yscale='log', title='(b) Same two test memberships')
    axes[1].legend(fontsize=9)
    for ax in axes:
        ax.grid(alpha=0.2, which='major')
        ax.set_xlim(.695, 1.005)
    save(fig, 'fig01_thresholds', 'Dependence and training feasibility as the lexical threshold changes. (a) Full upstream graph, projected onto all 21,457 DAppSCAN files; the vertical axis is logarithmic. Project-only includes declared project relations; clone-only includes lexical and exact-byte relations; their joint closure forms a large component even when each relation alone has small components. (b) Eligible training among the historical DAppSCAN files for the same two 1,062-file tests. A larger file count does not imply enough positives or valid semantic independence. String-aware normalization is used; all thresholds are reported.')

    fig, ax = plt.subplots(figsize=(7.0, 4.0), layout='constrained')
    for threshold, color, marker in zip([.7, .8, .9, .99], COLORS, ['o', 's', '^', 'D']):
        d = curves.query('normalization == "string_aware" and policy == "joint" and seed >= 0 and threshold == @threshold')
        agg = d.groupby('dapp_percent').giant_fraction.agg(['median', 'min', 'max'])
        full = curves.query('normalization == "string_aware" and policy == "joint" and cohort == "full_upstream_21950" and threshold == @threshold').iloc[0].giant_fraction
        agg.loc[100] = [full, full, full]
        agg = agg.sort_index()
        ax.plot(agg.index, agg['median'] * 100, color=color, marker=marker, markersize=4, label=f'Jaccard {threshold:.2f}')
        ax.fill_between(agg.index, agg['min'] * 100, agg['max'] * 100, color=color, alpha=.12)
    ax.set(xlabel='DAppSCAN source population retained (%)', ylabel='Largest component (% of selected DAppSCAN files)',
           xlim=(8, 102), ylim=(0, 100), title='Population coverage and joint component growth')
    ax.grid(alpha=.2)
    ax.legend(loc='lower right', ncol=2, fontsize=9)
    save(fig, 'fig02_population', 'Five predeclared nested hash samples retain 10–90% of the DAppSCAN source population; 100% is the common full endpoint. The other 493 reference files remain included. Lines show median and shading shows the minimum–maximum range across the five samples, not confidence intervals. Each proportion uses the selected DAppSCAN population as denominator. These label-blind source samples differ from the historical label-informed per-project cap.')

    ab = BASE / 'dependency_audit/graph_scope_ablation_recovered_20261025'
    conc = read(ab / 'component_concentration.csv')
    feas = read(ab / 'fixed_test_feasibility.csv')
    names = ['A_observed', 'B_historical_string_aware', 'C_uncapped_reference_string_aware', 'D_with_candidate_string_aware']
    labels = ['A: historical\n7,080', 'B: exhaustive\n7,080', 'C: all references\n21,950', 'D: + candidate\n24,131']
    vals = [conc[conc.graph == n].iloc[0].largest_component_files for n in names]
    fig, axes = plt.subplots(1, 2, figsize=(10.3, 3.5), layout='constrained')
    axes[0].bar(np.arange(4), vals, color=COLORS[0], width=.65)
    for i, v in enumerate(vals): axes[0].text(i, v + 65, f'{int(v):,}', ha='center', fontsize=9)
    axes[0].set(ylim=(0, 6700), ylabel='Files in largest projected component', title='(a) Same 6,587-file projection')
    for test, color, offset in [('outside_p90_seed2', COLORS[0], -.18), ('outside_p90_seed4', COLORS[1], .18)]:
        values = [feas.query('graph == @n and test_id == @test and `class` == "reentrancy"').iloc[0].joint_raw_train_files for n in names]
        axes[1].bar(np.arange(4) + offset, values, width=.34, color=color, label=f'Test {test[-1]}')
        for i, v in enumerate(values): axes[1].text(i + offset, v * 1.17, f'{int(v):,}', ha='center', fontsize=8)
    axes[1].set(yscale='log', ylim=(5, 14000), ylabel='Eligible training files (log scale)', title='(b) Same fixed tests')
    axes[1].legend(fontsize=9)
    for ax in axes:
        ax.set_xticks(np.arange(4), labels, fontsize=8)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
    save(fig, 'fig03_scope_ablation', 'Controlled scope ablation at Jaccard 0.8. A is the previously reported historical graph; B recomputes exhaustive dependencies on the same sources; C adds all upstream reference files; D also adds the external candidate. Every panel uses the same historical DAppSCAN projection or fixed test membership. Group relations are reconstructed within each population. A and B agree; the training reduction already occurs at C.')


def external_flow():
    # Counts are verified against the immutable source audit flow.
    root = BASE / 'external_audit/source_audit_full_20261025'
    meta = read(root / 'candidate_source_metadata.csv')
    assert len(meta) == 2181
    stage1 = meta[meta.source_id != 'smartbugs_curated']
    stage2 = stage1[stage1.reconciliation == 'matched']
    repeated = meta.contract_id.str.lower().duplicated(keep=False) | meta.file_hash.duplicated(keep=False)
    stage3 = stage2[~repeated.loc[stage2.index]]
    assert [len(meta), len(stage1), len(stage2), len(stage3)] == [2181, 2039, 2023, 1998]
    fig, ax = plt.subplots(figsize=(9.8, 2.3))
    ax.set(xlim=(0, 10), ylim=(0, 2.5)); ax.axis('off')
    boxes = [('2,181', 'Candidate paths'), ('2,039', 'Curated source excluded'), ('2,023', 'Identity issues quarantined'), ('1,998', 'Repeated identities excluded')]
    for i, (n, label) in enumerate(boxes):
        x = .1 + i * 2.5
        ax.add_patch(FancyBboxPatch((x, .75), 2.1, 1.15, boxstyle='round,pad=.08', facecolor='#eef4f8', edgecolor=COLORS[0], linewidth=1.2))
        ax.text(x + 1.05, 1.48, n, ha='center', va='center', fontsize=20, weight='bold')
        ax.text(x + 1.05, 1.0, label.replace(' source ', '\nsource ').replace(' issues ', '\nissues ').replace(' identities ', '\nidentities '), ha='center', va='center', fontsize=9)
        if i < 3:
            ax.add_patch(FancyArrowPatch((x + 2.22, 1.3), (x + 2.4, 1.3), arrowstyle='-|>', mutation_scale=12, color='#444444'))
    ax.text(5, .23, 'Diagnostic source cohort; independent expert adjudication is still pending', ha='center', fontsize=10)
    save(fig, 'fig06_external_flow', 'Source-reconciliation flow for the diagnostic external cohort. Exclusions are sequential: 142 curated-source files, 16 additional paths with unresolved records, and 25 additional repeated-identity paths. The original reconciliation audit found 17 problematic paths overall, one already removed in the first stage. The final 1,998 files are a provisional source cohort, not 1,998 independently verified ground-truth cases.')


def representation_figure():
    root = REV / 'representations/run_20261025_v1'
    variants = ['corrected_file_normalized', 'corrected_file_preserved',
                'library_interface_masked_normalized', 'library_interface_masked_preserved']
    coverage = read(root / 'coverage.csv')
    largest, informative, retained, positives, candidate = [], [], [], [], []
    for variant in variants:
        c = read(root / variant / 'component_concentration.csv')
        c = c.query('metric == "jaccard" and policy == "base" and threshold == .8 and population == "full_dappscan"')
        t = read(root / variant / 'training_feasibility.csv')
        t = t.query('metric == "jaccard" and policy == "base" and threshold == .8 and training_population == "historical_dappscan"')
        assert len(c) == len(t) == 1
        r, tr = c.iloc[0], t.iloc[0]
        cov = coverage.query('dataset == "dappscan" and representation == @variant').iloc[0]
        largest.append(100 * r.largest_component_share)
        informative.append(100 * cov.informative_files / cov.files)
        retained.append(int(tr.retained_with_informative_representation))
        positives.append((int(tr.reentrancy_proxy_positive_retained), int(tr.unchecked_proxy_positive_retained)))
        candidate.append(int(tr.candidate_informative_files))
    labels = ['Full source\nCollapsed tokens', 'Full source\nPreserved tokens',
              'Declared blocks masked\nCollapsed tokens', 'Declared blocks masked\nPreserved tokens']
    x = np.arange(4)
    fig, axes = plt.subplots(2, 1, figsize=(8.4, 6.3), layout='constrained')
    axes[0].bar(x - .18, largest, width=.34, color=COLORS[0], label='Largest component')
    axes[0].bar(x + .18, informative, width=.34, color=COLORS[2], label='Informative source representation')
    for i, (a, b) in enumerate(zip(largest, informative)):
        axes[0].text(i - .18, a + 1.2, f'{a:.2f}', ha='center', fontsize=9)
        axes[0].text(i + .18, b + 1.2, f'{b:.2f}', ha='center', fontsize=9)
    axes[0].set(ylim=(0, 115), ylabel='% of all 21,457 DAppSCAN files', title='(a) Dependence and representation coverage')
    axes[0].legend(loc='lower left', fontsize=9)
    axes[1].bar(x, retained, color=COLORS[0], width=.58)
    for i, (n, pos) in enumerate(zip(retained, positives)):
        axes[1].text(i, n + 25, f'{n:,}\n({pos[0]} / {pos[1]} proxy positives)', ha='center', fontsize=9)
    axes[1].set(ylim=(0, 1900), ylabel='Eligible informative historical training files',
                title='(b) Training separated from the same external cohort')
    for ax in axes:
        ax.set_xticks(x, labels, fontsize=9)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
    save(fig, 'fig04_representations', 'Factorial lexical sensitivity at Jaccard 0.8 with unchanged project and raw-identity relations. Collapsed tokens use historical identifier/number normalization; preserved tokens retain them. Masking removes explicitly declared library/interface blocks and concatenates the residual token stream; it is not verified library-origin removal or semantic analysis. All graph nodes remain. Empty representations produce no lexical shingles in all four variants. (a) Both quantities use all 21,457 DAppSCAN files as denominator. (b) Eligible, informative training files among the historical 6,587 after separation from the same 1,998-file external cohort; parentheses give reentrancy/unchecked proxy positives. External informative coverage is 1,998/1,998 for full representations and 1,995/1,998 for masked representations. These are graph and coverage results, not externally measured model performance. A separately reported segmented-mask control tests boundary-spanning shingles.')


if __name__ == '__main__':
    graph_figures()
    external_flow()
    representation_figure()
    (OUT / 'captions.json').write_text(json.dumps(CAPTIONS, indent=2) + '\n')
    (OUT / 'input_hashes.json').write_text(json.dumps(INPUTS, indent=2) + '\n')
    (OUT / 'README.md').write_text('# Figure provenance\n\nGenerated by `revision1/make_figures.py` from saved results. PDF and SVG are vector exports; PNG is a preview. Input hashes and complete captions accompany the figures. Shaded sample ranges are not confidence intervals.\n\n' + '\n\n'.join(f'## {name}\n\n{caption}' for name, caption in CAPTIONS.items()) + '\n')
