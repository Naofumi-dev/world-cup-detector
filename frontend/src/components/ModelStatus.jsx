// Model metrics card with an on-demand retrain button.
export default function ModelStatus({ model, onRetrain, retraining }) {
  if (!model) return null;
  const acc = Math.round(model.accuracy * 100);
  const baseAcc = Math.round(model.baseline_accuracy * 100);
  const when = new Date(model.trained_at).toLocaleString();

  return (
    <section className="card d5">
      <div className="card-head">
        <h2>Model</h2>
        <span className="tag">scikit-learn · logistic</span>
      </div>
      <div className="card-body">
        <div className="metrics">
          <div className="metric">
            <div className="k">Accuracy</div>
            <div className="v good">{acc}%</div>
            <div className="vs-base">baseline {baseAcc}%</div>
          </div>
          <div className="metric">
            <div className="k">Log loss</div>
            <div className="v">{model.log_loss}</div>
            <div className="vs-base">baseline {model.baseline_log_loss}</div>
          </div>
        </div>
        <div className="model-foot">
          <span className="when">
            {model.n_samples.toLocaleString()} matches · {when}
          </span>
          <button className="btn btn-ghost" onClick={onRetrain} disabled={retraining}>
            {retraining ? (
              <>
                <span className="spin" />&nbsp; Retraining
              </>
            ) : (
              "Retrain"
            )}
          </button>
        </div>
      </div>
    </section>
  );
}
