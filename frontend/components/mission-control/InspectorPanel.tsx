export function InspectorPanel() {
  return (
    <aside className="flex w-[280px] flex-col border-l border-[#EAEFF5] bg-white">
      <div className="border-b border-[#EAEFF5] px-4 py-3">
        <h3 className="text-[0.76rem] font-semibold uppercase tracking-wider text-[#9CA3AF]">Inspector</h3>
      </div>
      <div className="flex flex-1 items-center justify-center px-4">
        <div className="text-center">
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-[10px] bg-[#F8FAFC]">
            <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 15.75V18m-7.5-6.75h.008v.008H8.25v-.008Zm0 2.25h.008v.008H8.25V13.5Zm0 2.25h.008v.008H8.25v-.008Zm0 2.25h.008v.008H8.25V18Zm2.498-6.75h.007v.008h-.007v-.008Zm0 2.25h.007v.008h-.007V13.5Zm0 2.25h.007v.008h-.007v-.008Zm0 2.25h.007v.008h-.007V18Zm2.504-6.75h.008v.008h-.008v-.008Zm0 2.25h.008v.008h-.008V13.5Zm0 2.25h.008v.008h-.008v-.008Zm0 2.25h.008v.008h-.008V18Zm2.498-6.75h.008v.008h-.008v-.008Zm0 2.25h.008v.008h-.008V13.5Z" />
            </svg>
          </div>
          <p className="text-[0.8rem] font-medium text-[#9CA3AF]">No item selected</p>
          <p className="mt-1 text-[0.7rem] text-[#B0B7C3]">
            Select a mission, task, or artifact to inspect
          </p>
        </div>
      </div>
    </aside>
  )
}
