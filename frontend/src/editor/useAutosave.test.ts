import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { createSaveQueue, type SaveStatus } from "./useAutosave";

const DELAY = 800;
const RETRY = 3000;

/** A promise we resolve or reject by hand, to hold a save "in flight". */
function deferred() {
  let resolve!: () => void;
  let reject!: (err: unknown) => void;
  const promise = new Promise<void>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function setup(save: (html: string) => Promise<void>) {
  const statuses: Array<[SaveStatus, string | undefined]> = [];
  const queue = createSaveQueue(save, DELAY, (status, error) => statuses.push([status, error]));
  const last = () => statuses[statuses.length - 1];
  return { queue, statuses, last };
}

describe("createSaveQueue", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("collapses rapid edits into one save with the latest content", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { queue, last } = setup(save);

    queue.schedule("a");
    await vi.advanceTimersByTimeAsync(300);
    queue.schedule("ab");
    await vi.advanceTimersByTimeAsync(300);
    queue.schedule("abc");
    expect(save).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(DELAY);

    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith("abc");
    expect(last()).toEqual(["saved", undefined]);
    expect(queue.hasUnsaved()).toBe(false);
  });

  it("keeps one save in flight and sends only the newest content after it", async () => {
    const first = deferred();
    const save = vi.fn().mockReturnValueOnce(first.promise).mockResolvedValue(undefined);
    const { queue, last } = setup(save);

    queue.schedule("v1");
    await vi.advanceTimersByTimeAsync(DELAY);
    expect(save).toHaveBeenCalledTimes(1);

    queue.schedule("v2");
    await vi.advanceTimersByTimeAsync(DELAY);
    queue.schedule("v3");
    await vi.advanceTimersByTimeAsync(DELAY);
    expect(save).toHaveBeenCalledTimes(1); // still waiting on v1: no overlapping request
    expect(queue.hasUnsaved()).toBe(true);

    first.resolve();
    await vi.advanceTimersByTimeAsync(0);

    expect(save.mock.calls).toEqual([["v1"], ["v3"]]); // v2 was superseded, never sent
    expect(last()).toEqual(["saved", undefined]);
  });

  it.each([403, 404, 409])("stops retrying and reports failed on %i", async (status) => {
    const save = vi.fn().mockRejectedValue(new ApiError(status, "Cannot save"));
    const { queue, last } = setup(save);

    queue.schedule("text");
    await vi.advanceTimersByTimeAsync(DELAY);
    expect(last()).toEqual(["failed", "Cannot save"]);

    await vi.advanceTimersByTimeAsync(RETRY * 5);
    queue.schedule("more text");
    await vi.advanceTimersByTimeAsync(DELAY);

    expect(save).toHaveBeenCalledTimes(1);
    expect(queue.hasUnsaved()).toBe(true);
  });

  it("retries a 500 and then saves the same content", async () => {
    const save = vi.fn().mockRejectedValueOnce(new ApiError(500, "Internal server error")).mockResolvedValue(undefined);
    const { queue, last } = setup(save);

    queue.schedule("draft");
    await vi.advanceTimersByTimeAsync(DELAY);
    expect(last()).toEqual(["retrying", undefined]);
    expect(save).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(RETRY);

    expect(save.mock.calls).toEqual([["draft"], ["draft"]]);
    expect(last()).toEqual(["saved", undefined]);
    expect(queue.hasUnsaved()).toBe(false);
  });
});
